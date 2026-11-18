#!/usr/bin/env python3
"""vfx_atlas_packer.py - real-time VFX texture pipeline CLI.

Subcommands:
  extract-alpha    Black-background luminance -> straight (un-premultiplied) RGBA.
  stitch-flipbook  Sequential frames -> power-of-two NxN flipbook atlas (row-major, top-left origin).
  pack-channels    Up to 4 grayscale maps (or constants) -> one R/G/B[/A] packed texture.

Requires: Python 3.9+, Pillow >= 9.1, numpy.
Exit codes: 0 ok, 1 runtime/validation error, 2 CLI usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

LANCZOS = Image.Resampling.LANCZOS
IMG_EXT = {".png", ".tga", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp", ".exr", ".webp"}

LUMA_709 = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


class PackerError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- helpers

def natural_key(p: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def list_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise PackerError(f"not a directory: {folder}")
    files = sorted((p for p in folder.iterdir() if p.suffix.lower() in IMG_EXT), key=natural_key)
    if not files:
        raise PackerError(f"no images in {folder}")
    return files


def is_pow2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def floor_pow2(n: int) -> int:
    return 1 << (int(n).bit_length() - 1)


def load_rgba(path: Path) -> np.ndarray:
    """Load any image as float32 HxWx4 in [0,1], straight alpha."""
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.float32) / 255.0


def load_gray(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        if im.mode in ("I;16", "I;16B", "I;16L", "I"):
            a = np.asarray(im, dtype=np.float32)
            return a / (65535.0 if a.max() > 255 else 255.0)
        if im.mode in ("RGB", "RGBA", "P", "LA", "CMYK", "YCbCr"):
            rgb = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
            return rgb @ LUMA_709
        return np.asarray(im.convert("L"), dtype=np.float32) / 255.0


def to_image(arr: np.ndarray, mode: str) -> Image.Image:
    return Image.fromarray(np.clip(np.rint(arr * 255.0), 0, 255).astype(np.uint8), mode)


def premultiply(rgba: np.ndarray) -> np.ndarray:
    out = rgba.copy()
    out[..., :3] *= out[..., 3:4]
    return out


def unpremultiply(rgba: np.ndarray) -> np.ndarray:
    out = rgba.copy()
    a = out[..., 3:4]
    out[..., :3] = np.where(a > 1e-6, out[..., :3] / np.maximum(a, 1e-6), 0.0)
    return np.clip(out, 0.0, 1.0)


def resize_rgba(rgba: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Resize in premultiplied space so transparent black never bleeds into edges (no dark halos)."""
    pm = premultiply(rgba)
    chans = [np.asarray(Image.fromarray(pm[..., c], "F").resize(size, LANCZOS)) for c in range(4)]
    return unpremultiply(np.clip(np.stack(chans, axis=-1), 0.0, 1.0))


def resize_gray(g: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return np.clip(np.asarray(Image.fromarray(g.astype(np.float32), "F").resize(size, LANCZOS)), 0.0, 1.0)


def save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print(f"[ok] {path} {img.size[0]}x{img.size[1]} {img.mode}")


# ----------------------------------------------------------------------------- extract-alpha

def extract_alpha(rgba: np.ndarray, mode: str, black: float, white: float, gamma: float) -> np.ndarray:
    """Treat input as additive light over black. alpha = remapped intensity; color = rgb/alpha (straight).

    Compositing the result with standard alpha blending over black reproduces the source (within remap).
    """
    rgb = rgba[..., :3]
    inten = rgb.max(axis=-1) if mode == "max" else rgb @ LUMA_709
    a = np.clip((inten - black) / max(white - black, 1e-6), 0.0, 1.0) ** (1.0 / gamma)
    # Straight color: divide by the *raw* intensity peak so hue/saturation survive; clamp to [0,1].
    peak = np.maximum(rgb.max(axis=-1, keepdims=True), 1e-6)
    color = np.where(peak > 1e-6, rgb / peak, 0.0)
    return np.concatenate([np.clip(color, 0, 1), a[..., None]], axis=-1).astype(np.float32)


def cmd_extract_alpha(args) -> None:
    if not 0.0 <= args.black_point < args.white_point <= 1.0:
        raise PackerError("require 0 <= --black-point < --white-point <= 1")
    if args.gamma <= 0:
        raise PackerError("--gamma must be > 0")
    src = Path(args.input)
    if src.is_dir():
        files = list_images(src)
        out_dir = Path(args.output)
        if out_dir.suffix:
            raise PackerError("input is a folder; --output must be a folder")
        targets = [(f, out_dir / (f.stem + ".png")) for f in files]
    else:
        if not src.is_file():
            raise PackerError(f"input not found: {src}")
        targets = [(src, Path(args.output))]
    for f, out in targets:
        res = extract_alpha(load_rgba(f), args.mode, args.black_point, args.white_point, args.gamma)
        if args.white_rgb:
            res[..., :3] = 1.0  # grayscale-tint workflow: engine Color multiplies a white sprite
        save(to_image(res, "RGBA"), out)


# ----------------------------------------------------------------------------- stitch-flipbook

def select_frames(files: list[Path], cells: int, policy: str, hold_last: bool) -> list[Path | None]:
    n = len(files)
    if n >= cells:
        if policy == "first":
            return files[:cells]
        idx = np.rint(np.linspace(0, n - 1, cells)).astype(int)  # even temporal resample, keeps first+last
        return [files[i] for i in idx]
    if policy == "error":
        raise PackerError(f"{n} frames < {cells} cells (use --frame-policy even|first to pad)")
    return files + ([files[-1]] if hold_last else [None]) * (cells - n)


def union_alpha_bbox(frames: list[np.ndarray], thresh: float) -> tuple[int, int, int, int] | None:
    box = None
    for f in frames:
        ys, xs = np.nonzero(f[..., 3] > thresh)
        if xs.size == 0:
            continue
        b = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return box


def fit_into_cell(rgba: np.ndarray, cell: int, padding: int) -> np.ndarray:
    inner = cell - 2 * padding
    h, w = rgba.shape[:2]
    s = inner / max(w, h)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    scaled = resize_rgba(rgba, (nw, nh)) if (nw, nh) != (w, h) else rgba
    out = np.zeros((cell, cell, 4), np.float32)
    x0, y0 = (cell - nw) // 2, (cell - nh) // 2
    out[y0:y0 + nh, x0:x0 + nw] = scaled
    return out


def cmd_stitch_flipbook(args) -> None:
    m = re.fullmatch(r"([248])(?:x\1)?", args.grid.strip().lower())
    if not m:
        raise PackerError("--grid must be 2x2, 4x4 or 8x8")
    grid = int(m.group(1))
    if not is_pow2(args.max_size):
        raise PackerError("--max-size must be a power of two")
    if args.padding < 0:
        raise PackerError("--padding must be >= 0")
    files = list_images(Path(args.input))
    chosen = select_frames(files, grid * grid, args.frame_policy, args.pad_mode == "hold")
    frames = [load_rgba(f) if f is not None else None for f in chosen]
    ref = next(f for f in frames if f is not None)
    if any(f is not None and f.shape != ref.shape for f in frames):
        raise PackerError("all frames must share one resolution (render sequences at a fixed size)")

    if args.recenter:
        # One shared offset for the whole sequence: per-frame centering would add jitter to authored motion.
        box = union_alpha_bbox([f for f in frames if f is not None], args.alpha_threshold)
        if box is not None:
            x0, y0, x1, y1 = box
            side = max(x1 - x0, y1 - y0)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            sq = np.zeros((side, side, 4), np.float32)
            frames_c = []
            for f in frames:
                if f is None:
                    frames_c.append(None)
                    continue
                c = sq.copy()
                sx0, sy0 = cx - side // 2, cy - side // 2
                ix0, iy0 = max(sx0, 0), max(sy0, 0)
                ix1, iy1 = min(sx0 + side, f.shape[1]), min(sy0 + side, f.shape[0])
                c[iy0 - sy0:iy1 - sy0, ix0 - sx0:ix1 - sx0] = f[iy0:iy1, ix0:ix1]
                frames_c.append(c)
            frames = frames_c

    cell = args.cell or floor_pow2(max(ref.shape[:2]))
    if not is_pow2(cell):
        raise PackerError("--cell must be a power of two")
    cap_cell = args.max_size // grid
    if cell > cap_cell:
        print(f"[warn] cell {cell}px * {grid} > max {args.max_size}px; clamping cell to {cap_cell}px", file=sys.stderr)
        cell = cap_cell
    if 2 * args.padding >= cell:
        raise PackerError("--padding too large for cell size")

    atlas = np.zeros((cell * grid, cell * grid, 4), np.float32)
    for i, f in enumerate(frames):
        if f is None:
            continue
        r, c = divmod(i, grid)  # row-major, frame 0 = top-left (Unity TSA, Roblox Flipbook, VFX Graph Flipbook)
        atlas[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = fit_into_cell(f, cell, args.padding)

    out = Path(args.output)
    save(to_image(atlas, "RGBA"), out)
    meta = {
        "atlas": out.name, "grid": f"{grid}x{grid}", "cell_px": cell, "atlas_px": cell * grid,
        "frames_used": [p.name if p else None for p in chosen], "source_frame_count": len(files),
        "padding_px": args.padding, "order": "row-major, top-left origin",
    }
    if args.meta:
        Path(args.meta).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"[ok] {args.meta}")
    else:
        print(json.dumps(meta))


# ----------------------------------------------------------------------------- pack-channels

def parse_source(spec: str | None) -> float | Path | None:
    if spec is None:
        return None
    try:
        v = float(spec)
    except ValueError:
        p = Path(spec)
        if not p.is_file():
            raise PackerError(f"channel source not found: {spec}")
        return p
    if not 0.0 <= v <= 1.0:
        raise PackerError(f"constant channel value must be in [0,1]: {spec}")
    return v


def cmd_pack_channels(args) -> None:
    specs = {c: parse_source(getattr(args, c)) for c in "rgba"}
    if all(v is None for v in specs.values()):
        raise PackerError("provide at least one of --r --g --b --a")
    imgs = {c: load_gray(v) for c, v in specs.items() if isinstance(v, Path)}
    if args.size:
        size = (args.size, args.size)
    elif imgs:
        shapes = {g.shape for g in imgs.values()}
        h, w = max(s[0] for s in shapes), max(s[1] for s in shapes)
        size = (w, h)
    else:
        raise PackerError("all channels are constants; pass --size")
    if args.max_size and max(size) > args.max_size:
        f = args.max_size / max(size)
        size = (max(1, round(size[0] * f)), max(1, round(size[1] * f)))
    if not (is_pow2(size[0]) and is_pow2(size[1])):
        print(f"[warn] output {size[0]}x{size[1]} is not power-of-two (mip/compression inefficiency)", file=sys.stderr)

    w, h = size
    invert = set((args.invert or "").lower())
    if invert - set("rgba"):
        raise PackerError("--invert accepts letters from 'rgba' only")
    has_alpha = specs["a"] is not None
    chans = []
    for c in "rgba" if has_alpha else "rgb":
        v = specs[c]
        if v is None:
            g = np.zeros((h, w), np.float32)
        elif isinstance(v, float):
            g = np.full((h, w), v, np.float32)
        else:
            g = imgs[c] if imgs[c].shape == (h, w) else resize_gray(imgs[c], (w, h))
        chans.append(1.0 - g if c in invert else g)
    save(to_image(np.stack(chans, axis=-1), "RGBA" if has_alpha else "RGB"), Path(args.output))
    print("[note] import as linear data: Unity sRGB=OFF, Alpha Is Transparency=OFF; Blender Non-Color.")


# ----------------------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vfx_atlas_packer", description="Real-time VFX texture packing pipeline.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("extract-alpha", help="black-background luminance -> RGBA alpha")
    a.add_argument("input", help="image file or folder of images")
    a.add_argument("output", help="output .png file (or folder when input is a folder)")
    a.add_argument("--mode", choices=["luma", "max"], default="max",
                   help="intensity source: max(R,G,B) keeps saturated colors opaque (default); luma = Rec.709")
    a.add_argument("--black-point", type=float, default=0.02, help="intensity mapped to alpha 0 (kills noise floor)")
    a.add_argument("--white-point", type=float, default=1.0, help="intensity mapped to alpha 1")
    a.add_argument("--gamma", type=float, default=1.0, help=">1 thickens soft edges, <1 tightens")
    a.add_argument("--white-rgb", action="store_true", help="force RGB=white (tint in engine)")
    a.set_defaults(func=cmd_extract_alpha)

    s = sub.add_parser("stitch-flipbook", help="frames folder -> NxN power-of-two atlas")
    s.add_argument("input", help="folder of sequential frames (natural sort order)")
    s.add_argument("output", help="output atlas .png")
    s.add_argument("--grid", default="4x4", help="2x2 | 4x4 | 8x8")
    s.add_argument("--cell", type=int, default=0, help="cell px (power of two); default = floor_pow2(frame size)")
    s.add_argument("--max-size", type=int, default=4096, help="atlas cap px; use 1024 for Roblox")
    s.add_argument("--padding", type=int, default=0, help="transparent gutter px inside each cell (mip bleed guard)")
    s.add_argument("--frame-policy", choices=["even", "first", "error"], default="even",
                   help="more frames than cells: even=temporal resample, first=truncate; fewer: error or pad")
    s.add_argument("--pad-mode", choices=["empty", "hold"], default="empty", help="fill for missing cells")
    s.add_argument("--recenter", action="store_true", help="center union alpha bbox of the sequence")
    s.add_argument("--alpha-threshold", type=float, default=0.01, help="alpha cutoff for --recenter bbox")
    s.add_argument("--meta", help="write JSON metadata sidecar to this path")
    s.set_defaults(func=cmd_stitch_flipbook)

    c = sub.add_parser("pack-channels", help="grayscale maps -> R/G/B[/A] packed texture")
    c.add_argument("output", help="output .png")
    for ch, role in zip("rgba", ["primary shape/alpha", "erosion/dissolve noise", "UV distortion/flow mask",
                                 "emissive mask (optional)"]):
        c.add_argument(f"--{ch}", help=f"{ch.upper()} = {role}: image path or constant 0..1")
    c.add_argument("--size", type=int, default=0, help="force square output size px")
    c.add_argument("--max-size", type=int, default=0, help="downscale cap px (1024 for Roblox)")
    c.add_argument("--invert", default="", help="channels to invert, e.g. 'g' or 'gb'")
    c.set_defaults(func=cmd_pack_channels)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except PackerError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
