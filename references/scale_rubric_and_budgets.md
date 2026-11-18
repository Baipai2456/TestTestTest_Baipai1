---
id: scale_rubric_and_budgets
used_in: [STATE_0, STATE_3, STATE_4]
sections: [RUBRIC, LEVEL_RESOLUTION, BUDGETS, SHADER_MATH, TIMING, TEXTURE_MEMORY, AUDIT]
tiers: {T1: "levels 1-3", T2: "levels 4-7", T3: "levels 8-10"}
note: Budgets are production guidelines per single effect instance at peak, not engine hard limits (hard limits are listed in platform files).
---

# 1-10 SCALE RUBRIC, PERFORMANCE BUDGETS, SHADER MATH

<RUBRIC>
| Lvl | Layers | Flipbook | Atlas px | Texture packing | Shader / platform features | Agent mode | Refinement iterations | Est. tokens (context+output) |
|---|---|---|---|---|---|---|---|---|
| 1 | 1-2 (L1 + L3) | none or 2x2 | 256 | none; procedural sprite | Unlit additive; size/alpha over life | single, sequential | 0 | 3k-8k |
| 2 | 2 | 2x2 | 256-512 | none | + color over life ramp | single | 0 | 6k-12k |
| 3 | 3 (L1+L2+L3) | 2x2 | 512 | optional R/G mask | + simple erosion (Unity/Blender); Roblox: OneShot flipbook | single | 1 | 10k-18k |
| 4 | 3-4 | 4x4 | 512 | R/G/B packed | + UV distortion scroll; soft particles | 2 lanes | 1 | 15k-25k |
| 5 | 3-4 (L0+L1+L2/L3+L4) | 4x4 | 512-1024 | R/G/B packed noise/erosion | custom UV distortion + lifetime alpha erosion (Custom1.x); point light flash | 2 lanes parallel | 1 | 20k-35k |
| 6 | 4-5 | 4x4 | 1024 | R/G/B packed + separate tileable noise | + edge glow; flipbook + noise modes; light curve | 2 lanes | 2 | 30k-45k |
| 7 | 5 | 4x4 / 8x8 core | 1024 | R/G/B(+A) | + heat-haze (Unity) / beam scroll (Roblox); camera shake | 2-3 lanes | 2 | 40k-60k |
| 8 | 5+ | 8x8 core, 4x4 others | 1024-2048 (Roblox 1024) | R/G/B/A | + flipbook frame blending (UV2/AnimBlend), Blender baked ring/trail meshes | 3 lanes + review | 2/layer | 55k-85k |
| 9 | 5+ (+ sub-layers) | 8x8 | 2048 (Roblox 1024) | R/G/B/A + flowmap | + flowmaps, mesh particles, VFX Graph option, light + shake sync | 3 lanes + review | 2/layer | 70k-110k |
| 10 | 5+ synchronized, sub-emitters | high-FPS 8x8 | 2048 (Roblox 1024) | R=Alpha, G=Erosion, B=Distortion, A=EmissiveMask | custom Shader Graph / Geometry Nodes / Luau choreography + camera shake/lighting sync | full multi-agent + iterative refinement | 2/layer + final pass | 80k-150k |
CANONICAL BENCHMARKS (verbatim source for SKILL.md STATE_0):
- Level 1 (Rapid Prototype / Low-Cost): 1–2 layers; single static procedural texture or `2x2` flipbook (`256x256`); basic Unlit/Additive material; single-pass generation; minimal token usage; ultra-low GPU overdraw.
- Level 5 (Production Indie Standard): 3–4 layers (Anticipation + Core + Trail/Sparks + Smoke); `4x4` flipbook (`512x512` or `1024x1024`) + channel-packed noise/erosion mask; custom UV distortion & lifetime alpha-erosion shader; 2-agent parallel execution; balanced draw calls.
- Level 10 (AAA Hero / Cinematic Showcase): 5+ synchronized layers; high-FPS `8x8` flipbooks + custom baked Blender meshes/flowmaps; multi-channel packed textures (`R=Alpha, G=Erosion, B=Distortion, A=EmissiveMask`); custom Shader Graph / Geometry Nodes / Luau choreography scripts + camera shake/lighting synchronization; full multi-agent pipeline with iterative refinement.
TIME BUDGET (1-10) -> iteration allowance: 1-2: one pass, no audit loop; 3-5: one audit loop; 6-8: two loops; 9-10: two loops per layer + final review.
TOKEN BUDGET (1-10) -> verbosity: 1-3: tables only, one config variant, no alternatives; 4-7: full configs + one alternative; 8-10: full configs, variants, rationale, test matrix.
</RUBRIC>

<LEVEL_RESOLUTION>
effective_level = clamp(min(quality, time_budget + 2, token_budget + 2), 1, 10)
tier = T1 if effective_level <= 3 else T2 if effective_level <= 7 else T3
Examples: (Q10,T5,K9) -> 7 (time caps); (Q4,T1,K1) -> 3; (Q8,T8,K8) -> 8.
</LEVEL_RESOLUTION>

<BUDGETS>
UNITY URP (per effect instance, at peak):
| Metric | T1 PC | T1 Mobile | T2 PC | T2 Mobile | T3 PC | T3 Mobile |
|---|---|---|---|---|---|---|
| max_draw_calls (layers + light) | 2 | 2 | 6 | 4 | 12 | 6 |
| max_live_particles (Shuriken) | 50 | 30 | 300 | 120 | 2000 | 300 |
| max_live_particles (VFX Graph) | — | — | 5000 | n/a | 50000 | n/a |
| max_overdraw_layers (hotspot) | 3 | 2 | 6 | 4 | 10 | 5 |
| max_texture_memory_mb (incl. mips) | 1 | 0.5 | 6 | 3 | 24 | 8 |
| texture samples per fragment | 1 | 1 | 2 | 2 | 4 | 2 |
| realtime lights | 0 | 0 | 1 | 0-1 | 2 | 1 |
ROBLOX (per effect instance, at peak):
| Metric | T1 | T2 | T3 |
|---|---|---|---|
| max_draw_calls (= emitter + beam + trail instances) | 3 | 6 | 12 |
| max_live_particles | 40 | 150 | 400 |
| max_overdraw_layers (hotspot, formula estimate) | 2 | 4 | 6 |
| textures (each <= 1024) | 1 | 3 | 6 |
| PointLights | 0-1 | 1 | 2 |
| largest L1 particle size (studs, relative to 5-stud character) | 6 | 10 | 16 |
| max_texture_memory_mb (engine-managed; count 4 MB per 1024 RGBA) | 1 | 12 | 24 |
BLENDER BAKE:
| Metric | T1 | T2 | T3 |
|---|---|---|---|
| frames | 4 | 16 | 64 |
| cell px rendered | 128-256 | 256 | 256-512 (render 2x, downsample) |
| EEVEE render samples | 16 | 32 | 64 |
| GN mesh tris exported per effect mesh | 500 | 1000 | 2000 |
</BUDGETS>

<SHADER_MATH>
| Formula | Expression | Notes |
|---|---|---|
| Lifetime erosion | `t = lerp(-s, 1, age); a = saturate((E - t) / s)` | age = Custom1.x (Unity), animated threshold (Blender); s = softness 0.05-0.3; at age 0 fully visible, at age 1 fully eroded |
| Burn edge band | `edge = saturate(1 - abs(E - (t + s)) / w) * shape` | w = edge width; add `edge * EdgeColorHDR` |
| UV distortion | `uv' = uv + (D * 2 - 1) * k * amount` | D = B channel / noise; k <= padding_px / cell_px on flipbooks |
| Noise scroll | `uvN = uv * tiling + time * scroll` | scroll in UV/s |
| Soft particle / depth fade | `f = saturate((SceneEyeDepth - FragEyeDepth) / fadeDist)` | Unity: SceneDepth(Eye) - ScreenPosition(Raw).w |
| Flipbook cell (Unity UV origin bottom-left; atlas frame 0 top-left) | `i = floor(p * N*N); col = i mod N; row = floor(i / N); uvA = (uv + float2(col, N-1-row)) / N` | p = normalized playback 0..1 |
| Flipbook frame blend | `c = lerp(sample(i), sample(i+1), frac(p * N*N))` | Unity: UV2 + AnimBlend streams |
| Fresnel rim | `F = pow(1 - saturate(dot(N, V)), P)` | P = 2-5 |
| HDR intensity (Unity color picker) | `linearColor * 2^intensity` | intensity 1 = x2; L1 core 2^2..2^3 |
| Luminance (Rec.709) | `Y = 0.2126 R + 0.7152 G + 0.0722 B` | packer `--mode luma` |
| Straight alpha from black-bg additive | `a = remap(max(R,G,B)); rgb = src / max(R,G,B)` | packer `extract-alpha --mode max`; over-black composite reproduces source |
| Additive blend | `dst = dst + src.rgb * src.a` | order-independent; overdraw cost unchanged |
| Alpha blend | `dst = src.rgb * src.a + dst * (1 - src.a)` | order-dependent; sort layers |
| Premultiplied | `dst = src.rgb + dst * (1 - src.a)` | allows additive + occluding in one material |
| Overdraw estimate | `overdraw ≈ Σ(particle_screen_area * count) / effect_screen_area` | target <= max_overdraw_layers |
</SHADER_MATH>

<TIMING>
EASING (t in 0..1):
| Name | f(t) | Use |
|---|---|---|
| ease_out_cubic | `1 - (1 - t)^3` | scale-up of bursts, shockwave radius |
| ease_out_expo | `t == 1 ? 1 : 1 - 2^(-10t)` | flashes, light decay inverse |
| decay_quad | `(1 - t)^2` | alpha decay, shake decay |
| anticipation | `t^2` (inward) | L0 converge speed |
REFERENCE DURATIONS (s, impact-class effects):
| Effect class | L0 preroll | L1 attack | L1 total | L2 | L3 | L4 |
|---|---|---|---|---|---|---|
| Light hit / spark | 0 | 0.016-0.033 | 0.15 | 0.15 | 0.3 | 0.0-0.3 |
| Medium impact / spell hit | 0.1-0.25 | 0.033 | 0.4 | 0.45 | 0.8 | 1.2 |
| Heavy explosion | 0.25-0.5 | 0.05 | 0.6 | 0.6 | 1.2 | 2.5-4 |
| Slash | 0.05 | 0.016 | 0.2 (arc) | 0.25 | 0.3 | 0.4 |
FLIPBOOK FPS: core bursts 24-30; flames loop 16-24; smoke 8-12. Frames available = grid^2; OneShot spreads frames over particle lifetime.
RULE: L1 peak reached within 3 frames @60 fps of impact. Light attack <= L1 attack. Camera shake duration <= 0.5 s for non-cinematic.
</TIMING>

<TEXTURE_MEMORY>
| Format | bpp | 1024² size (no mips) | Use |
|---|---|---|---|
| RGBA32 | 32 | 4.0 MiB | uncompressed; Roblox estimate |
| BC7 / BC3 (DXT5) | 8 | 1.0 MiB | color+alpha flipbooks, RGBA packs |
| BC1 (DXT1) | 4 | 0.5 MiB | RGB packs (lower per-channel precision: 5/6/5-bit endpoints) |
| BC4 | 4 | 0.5 MiB | single-channel mask |
| BC5 | 8 | 1.0 MiB | flowmap RG |
| ASTC 4x4 / 6x6 / 8x8 | 8 / 3.56 / 2 | 1.0 / 0.45 / 0.25 MiB | mobile |
Mipmaps: x 1.333.
CHANNEL PACKING SAVINGS:
- 3 masks (shape, erosion, distortion) as 3x BC4 = 12 bpp + 3 samplers -> 1x BC1 RGB = 4 bpp + 1 sampler => 66.7% memory saved, 3 -> 1 texture fetch/binding.
- 4 masks as 4x BC4 = 16 bpp -> 1x BC7 RGBA = 8 bpp => 50% saved, 4 -> 1 fetch.
- Precision trade-off: BC1 cross-channel artifacts can band erosion thresholds; use BC7 when erosion banding is visible.
- Roblox: not applicable (no custom shader sampling; see platforms/roblox_studio.md RB03).
</TEXTURE_MEMORY>

<AUDIT>
Run in STATE_4 against the tier budgets. Output `check | budget | actual | PASS/FAIL | fix`.
| ID | Check | Applies |
|---|---|---|
| A01 | Draw calls / emitter instances at peak <= max_draw_calls | all |
| A02 | Live particles at peak <= max_live_particles | all |
| A03 | Overdraw hotspot <= max_overdraw_layers (Unity overdraw view; Roblox estimate via formula) | unity, roblox |
| A04 | Texture memory <= max_texture_memory_mb | all |
| A05 | All textures power-of-two; Roblox <= 1024 | all |
| A06 | Data textures linear (sRGB OFF / Non-Color); color textures sRGB | unity, blender |
| A07 | Value hierarchy: only L1 exceeds bloom threshold | all |
| A08 | Every layer alpha/transparency reaches invisible at end of life (no pop) | all |
| A09 | L1 peak within 3 frames @60 fps of impact; L0 precedes impact | all |
| A10 | Vertex streams match shader channels (Custom1.xy -> TEXCOORD0.zw) | unity |
| A11 | FlipbookIncompatible empty for every flipbook emitter; layout matches atlas grid | roblox |
| A12 | ZOffset / sorting monotonic with render_order; no Z-fighting flicker | unity, roblox |
| A13 | No fabricated asset IDs; unset IDs produce runtime warnings | roblox |
| A14 | Cleanup: instances destroyed/pooled after max lifetime (Debris / destroyWhenFinished) | unity, roblox |
| A15 | Bake frames: safe-area respected (no cell-edge clipping), last frame faded | blender |
| A16 | Distortion amplitude <= padding_px / cell_px on flipbooks (no neighbor-cell bleed) | unity |
FAIL handling: fix the cheapest lever first (count -> size -> lifetime -> resolution -> layer removal). Never remove L1. Report residual FAILs after 2 loops with the reason.
</AUDIT>
