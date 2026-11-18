---
id: asset_subagent_prompts
roles: [SA1_2D_Asset_Generator, SA2_Pipeline_Processor, SA3_Platform_Specialist_contract]
used_in: [STATE_1.branch_B, STATE_3]
inputs: manifest (agents/vfx_architect_schema.md §MANIFEST_SCHEMA)
outputs: textures on #000000 + handoff block
---

# SUB-AGENT DIRECTIVES — 2D ASSETS, PROMPT ENGINEERING, PIPELINE PROCESSING

<universal_image_rules>
APPLY TO EVERY GENERATED IMAGE:
- Background: pure black #000000, flat, no vignette, no gradient, no floor, no environment.
- Single isolated subject, centered, fully inside frame with >= 8% margin on every side (no edge clipping).
- Orthographic/flat front view unless the manifest requests a perspective sprite.
- No text, no watermark, no UI, no characters, no hands, no weapons (unless the effect is attached geometry).
- Grayscale requested => monochrome luminance only; color is applied in-engine via ramps/tints.
- Value structure: brightest at the focal core, smooth falloff to black; avoid large uniform mid-gray areas (they become semi-transparent haze after extract-alpha).
- Square aspect 1:1. Request the largest square the generator supports; the packer downsamples.
NEGATIVE TOKENS (append when the generator supports negatives): "background scenery, ground, horizon, text, watermark, signature, frame border, vignette, lens flare spill across frame, cropped, cut off, motion blur smear across frame, photo, realistic person".
</universal_image_rules>

<CONCEPT_PROMPT used_in="STATE_1.branch_B">
TEMPLATE (fill every <slot>; English for the generator regardless of user language):
```
Game VFX concept, <effect_name>: <one-sentence action>. Stylization: <stylized | semi-realistic | anime | painterly>.
Isolated single effect at the exact peak-action keyframe, centered, clear readable silhouette shaped as <silhouette.shape>,
strong value contrast with a white-hot core fading to <color_ramp.mid hex> then <color_ramp.edge hex> edges,
visible secondary elements: <L2 description>, <L3 description>, faint <L4 description>.
Pure black #000000 background, no environment, no ground, no text, orthographic front view, square 1:1, high detail.
```
EXAMPLE:
```
Game VFX concept, FireballImpact: a fireball detonates on contact. Stylization: stylized.
Isolated single effect at the exact peak-action keyframe, centered, clear readable silhouette shaped as radial burst,
strong value contrast with a white-hot core fading to #FF8A1F then #7A1400 edges,
visible secondary elements: thin expanding shockwave ring, sharp flying ember sparks, faint dark smoke puffs.
Pure black #000000 background, no environment, no ground, no text, orthographic front view, square 1:1, high detail.
```
</CONCEPT_PROMPT>

<SA1 name="2D Asset Generator">
INPUT: manifest.textures[] where source in {generate, procedural}.
DECISION TABLE:
| texture.kind | tileable | Preferred source | Fallback |
|---|---|---|---|
| noise | true | §PROCEDURAL_FALLBACK `noise`/`cells` (exact seamless) | generator with "seamless tileable" prompt, then verify seam |
| packed_mask channel | any | procedural or Blender bake | generator grayscale |
| gradient | false | procedural (`disc`, `ring`, `streak`) | — |
| color_sprite | false | procedural + extract-alpha --white-rgb | generator |
| flipbook | false | Blender bake (platforms/blender_vfx.md) | generator sequence (§FLIPBOOK_PROMPTS) |
| flowmap | true/false | Blender bake | — (never generate flowmaps with image models: vectors must be exact) |
RULES:
- Image models cannot guarantee temporal consistency. For flipbooks at effective_level >= 5 prefer Blender bake. Use generated sequences only for effective_level <= 4 or stylized effects that tolerate boil.
- Name files exactly: `<texture.id>__<channel|frame>_<NNNN>.png` (4-digit, 0-based, natural sort-safe).
- Output to `raw/<texture.id>/`.

<GRAYSCALE_MASK_PROMPTS>
```
SHAPE MASK: Grayscale alpha mask for a game particle texture: <shape: soft round puff | sharp four-point star | crescent slash arc | jagged shard | wispy smoke wisp | radial shockwave ring>.
Pure white subject on pure black #000000, smooth falloff edges, centered, square 1:1, no texture noise unless specified, no color.

EROSION NOISE: Seamless tileable grayscale noise texture for dissolve erosion, <billowy cloud fBm | cellular voronoi cracks | streaky fibrous>,
full 0-255 value range, evenly distributed values, no visible tiling seams, no focal point, square 1:1.

DISTORTION/FLOW MASK: Seamless tileable soft grayscale noise for UV distortion, low frequency large blobs, smooth gradients,
no hard edges, mid-gray average, square 1:1.

EMISSIVE MASK: Grayscale emissive mask: bright thin hot edges and inner core of a <shape>, everything else black #000000, square 1:1.
```
</GRAYSCALE_MASK_PROMPTS>

<FLIPBOOK_PROMPTS>
Generate N = grid^2 frames (or more; packer resamples evenly). Lock everything except the phase:
```
Frame <i+1> of <N> of a game VFX sprite sequence: <effect description>.
Phase: <phase_table[i]>. Identical camera, identical scale reference, identical centering, identical lighting and style as all other frames.
Pure black #000000 background, monochrome grayscale (white-hot core), isolated, centered, square 1:1, no text.
```
PHASE TABLE (map i/N -> phase text):
| i/N | Phase |
|---|---|
| 0.00-0.10 | "ignition: small, very bright compact core" |
| 0.10-0.25 | "peak expansion: maximum brightness, crisp silhouette" |
| 0.25-0.50 | "breakup: core fragments, edges tear into wisps" |
| 0.50-0.80 | "dissipation: dimmer, larger, hollow center, wispy edges" |
| 0.80-1.00 | "fade: faint thin remnants, mostly black" |
CONSISTENCY GUARD: if the generator supports seeds / image-to-image, fix seed and feed frame i-1 as init image with strength 0.35-0.5.
QA: reject frames whose union alpha bbox center deviates > 10% of frame size from the sequence median; regenerate or use `stitch-flipbook --recenter`.
</FLIPBOOK_PROMPTS>

<PROCEDURAL_FALLBACK>
Deterministic generator for when no image model exists or exact tiling is required. Save as `scripts/procedural_maps.py` in the user's working copy only when needed (not part of the shipped repo tree). Requires numpy + Pillow.
```python
#!/usr/bin/env python3
# procedural_maps.py - deterministic grayscale VFX maps (numpy + Pillow). All outputs 8-bit L, power-of-two.
# usage: python procedural_maps.py <kind> <out.png> [--size 512] [--seed 0] [--scale 8] [--beta 2.0]
# kinds: noise (seamless fBm via spectral synthesis), disc, ring, streak, cells (seamless Worley F1)
import argparse
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("kind", choices=["noise", "disc", "ring", "streak", "cells"])
ap.add_argument("out")
ap.add_argument("--size", type=int, default=512)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--scale", type=float, default=8.0, help="noise: low-freq cutoff; cells: cells per side")
ap.add_argument("--beta", type=float, default=2.0, help="noise spectral falloff: 1=detailed, 3=smooth")
ap.add_argument("--softness", type=float, default=0.35, help="disc/ring/streak edge falloff 0..1")
a = ap.parse_args()
n = a.size
assert n > 0 and n & (n - 1) == 0, "--size must be a power of two"
rng = np.random.default_rng(a.seed)
y, x = (np.mgrid[0:n, 0:n] + 0.5) / n  # [0,1)


def norm(v):
    v = v - v.min()
    return v / max(v.max(), 1e-8)


if a.kind == "noise":
    # Periodic by construction: inverse FFT of shaped white-noise spectrum tiles seamlessly.
    f = np.fft.fftfreq(n) * n
    r = np.sqrt(f[None, :] ** 2 + f[:, None] ** 2)
    amp = np.where(r > 0, 1.0 / np.maximum(r, a.scale / 4) ** (a.beta / 2 + 0.5), 0.0)
    spec = amp * np.exp(2j * np.pi * rng.random((n, n)))
    img = norm(np.real(np.fft.ifft2(spec)))
elif a.kind == "cells":
    k = max(1, int(a.scale))
    pts = rng.random((k * k, 2))
    d = np.full((n, n), np.inf)
    for px, py in pts:  # wrap distance => seamless
        dx = np.abs(x - px); dx = np.minimum(dx, 1 - dx)
        dy = np.abs(y - py); dy = np.minimum(dy, 1 - dy)
        d = np.minimum(d, np.sqrt(dx * dx + dy * dy))
    img = norm(d)
else:
    cx, cy = x - 0.5, y - 0.5
    rad = np.sqrt(cx * cx + cy * cy) * 2  # 0 center, 1 at cell edge
    s = max(a.softness, 1e-3)
    if a.kind == "disc":
        img = np.clip((1 - rad) / s, 0, 1) ** 2
    elif a.kind == "ring":
        img = np.clip(1 - np.abs(rad - 0.75) / (0.2 * s + 0.02), 0, 1) ** 2
    else:  # streak: horizontal spark, bright core
        img = np.clip(1 - np.abs(cx) * 2, 0, 1) ** 1.5 * np.clip(1 - np.abs(cy) / (0.08 * s + 0.01), 0, 1) ** 2
Image.fromarray(np.rint(np.clip(img, 0, 1) * 255).astype(np.uint8), "L").save(a.out)
print(f"[ok] {a.out} {a.kind} {n}x{n}")
```
RECIPES:
| Need | Command |
|---|---|
| Erosion noise (G) | `python procedural_maps.py noise raw/ero.png --size 512 --scale 6 --beta 2.2 --seed 1` |
| Distortion noise (B) | `python procedural_maps.py noise raw/dist.png --size 512 --scale 3 --beta 3.0 --seed 2` |
| Crack erosion | `python procedural_maps.py cells raw/cracks.png --size 512 --scale 8 --seed 3` |
| Core puff shape (R) | `python procedural_maps.py disc raw/shape.png --size 512 --softness 0.8` |
| Shockwave ring | `python procedural_maps.py ring raw/ring.png --size 512 --softness 0.5` |
| Spark sprite | `python procedural_maps.py streak raw/spark.png --size 128 --softness 0.6` |
</PROCEDURAL_FALLBACK>

<QA_CHECKS owner="SA1" run="before handoff">
Q1 corners: mean of 4 corner 8x8 patches <= 3/255 (black background intact). Exception: tileable noise.
Q2 seam (tileable only): mean |col0 - col_last| and |row0 - row_last| <= 2.5x mean adjacent-pixel difference.
Q3 dynamic range: noise maps use >= 90% of 0..255 (p1 <= 13, p99 >= 242). Otherwise normalize.
Q4 dimensions: square; power of two after packing.
Q5 flipbook monotonic energy: summed luminance per frame peaks within first 30% of frames for burst-type effects.
Report Q-check results in handoff.unverified when not executed.
</QA_CHECKS>

<SA2 name="Python Pipeline Processor">
TOOL: `python scripts/vfx_atlas_packer.py <subcommand> ...` (Pillow + numpy). Exit 0 = ok, 1 = validation/runtime error, 2 = CLI usage.
EXECUTE manifest.textures[].pipeline in order. Then return handoff with produced paths + stitched JSON meta.
SUBCOMMAND CONTRACTS:
| Subcommand | Input | Output | Key flags |
|---|---|---|---|
| extract-alpha | file or folder (black bg) | straight-alpha RGBA PNG(s) | `--mode max` (default; saturated colors stay opaque) / `luma`; `--black-point 0.02` noise floor; `--gamma`; `--white-rgb` for engine-tinted sprites |
| stitch-flipbook | folder of frames (natural sort) | NxN atlas PNG, row-major, frame 0 top-left | `--grid 2x2/4x4/8x8`; `--cell` px; `--max-size` (1024 Roblox); `--padding` px; `--frame-policy even/first/error`; `--pad-mode empty/hold`; `--recenter`; `--meta` json |
| pack-channels | up to 4 grayscale paths or constants 0..1 | RGB or RGBA PNG | `--r/--g/--b/--a`; `--invert gb`; `--size`; `--max-size` |
PLATFORM RECIPES:
```bash
# Unity / Blender: channel-packed mask (R=shape, G=erosion, B=distortion[, A=emissive])
python scripts/vfx_atlas_packer.py pack-channels out/T_FX_Mask.png --r raw/shape.png --g raw/ero.png --b raw/dist.png --size 512
# Unity: color flipbook 8x8 at 2048 (cell 256)
python scripts/vfx_atlas_packer.py stitch-flipbook frames/core out/T_FX_Core.png --grid 8x8 --cell 256 --max-size 2048 --padding 2 --meta out/T_FX_Core.json
# Roblox: additive flipbook from black-bg render, white RGB so ParticleEmitter.Color tints it
python scripts/vfx_atlas_packer.py extract-alpha frames/core alpha/core --mode max --white-rgb
python scripts/vfx_atlas_packer.py stitch-flipbook alpha/core out/T_FX_Core.png --grid 4x4 --max-size 1024 --padding 2
# Roblox: colored (pre-tinted) flipbook, keep authored hues
python scripts/vfx_atlas_packer.py extract-alpha frames/core alpha/core --mode max
python scripts/vfx_atlas_packer.py stitch-flipbook alpha/core out/T_FX_CoreColor.png --grid 8x8 --max-size 1024
```
RULES:
- Renders with real alpha (Blender `--mode alpha`) skip extract-alpha.
- extract-alpha output color is straight (un-premultiplied); never premultiply again in the packer.
- Cell clamp warnings (`[warn] ... clamping cell`) must be recorded as handoff.deviations.
- Never upscale a source more than 2x to reach a cell size; reduce cell size instead and record a deviation.
</SA2>

<SA3_CONTRACT name="Platform Specialist">
LOAD: only `platforms/<manifest.platform>.md` (for blender->X: blender_vfx.md then X file).
INPUT: manifest + SA2 handoff (actual cell_px, grid, channel map, paths).
OUTPUT ORDER: (1) import settings table per texture, (2) shader/material blueprint, (3) emitter/particle config per layer (L0..L4), (4) control script, (5) hierarchy tree, (6) test procedure.
RULE: use SA2 actual values when they differ from the manifest; list each in handoff.deviations.
</SA3_CONTRACT>
