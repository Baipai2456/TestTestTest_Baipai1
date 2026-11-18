---
id: scale_rubric_and_budgets
used_in: [STATE_0, STATE_3, STATE_4]
sections: [RUBRIC, LEVEL_RESOLUTION, WORK_CONTRACT, QUALITY_REVIEW, OPTIMIZATION_PROFILES, SHADER_MATH, TIMING, TEXTURE_MEMORY, AUDIT]
tiers: {T1: "levels 1-3", T2: "levels 4-7", T3: "levels 8-10"}
profiles: {showcase: "optimization 1-3", standard: "optimization 4-7", strict: "optimization 8-10"}
note: Budgets are production guidelines per single effect instance at peak, not engine hard limits (hard limits are listed in platform files). Quality level and optimization are independent axes.
---

# 1-10 SCALE RUBRIC, WORK CONTRACT, QUALITY REVIEW, OPTIMIZATION PROFILES, SHADER MATH

<RUBRIC>
Feature scope per effective_level. Work depth (variants, loops, time) is in §WORK_CONTRACT.
| Lvl | Layers | Flipbook source | Flipbook / atlas | Texture packing | Shader / platform features |
|---|---|---|---|---|---|
| 1 | 1-2 (L1 + L3) | procedural sprite | none or 2x2 @256 | none | Unlit additive; size/alpha over life |
| 2 | 2 | procedural / Blender shader bake | 2x2 @256-512 | none | + color over life ramp |
| 3 | 3 (L1+L2+L3) | Blender shader bake | 2x2-4x4 @512 | optional R/G mask | + simple erosion (Unity/Blender); Roblox: OneShot flipbook |
| 4 | 3-4 | Blender shader bake | 4x4 @512 | R/G/B packed | + UV distortion scroll; soft particles |
| 5 | 3-4 (L0+L1+L2/L3+L4) | Blender shader bake | 4x4 @512-1024 | R/G/B packed noise/erosion | custom UV distortion + lifetime alpha erosion (Custom1.x); point light flash |
| 6 | 4-5 | Blender shader bake, tuned | 4x4 @1024 | R/G/B packed + separate tileable noise | + burn edge glow; light curve |
| 7 | 5 | Blender shader bake, tuned; Geometry Nodes ring/trail meshes | 4x4 + 8x8 core @1024 | R/G/B(+A) | + heat-haze (Unity) / beam scroll (Roblox); camera shake; High + Low LOD |
| 8 | 5 + sub-layers | Mantaflow sim (sim-res 128) for fire/smoke; shader bake for the rest | 8x8 core @2048 (Roblox 1024) | R/G/B/A | + flipbook frame blending (UV2/AnimBlend), baked ring/trail meshes, H/M/L LODs |
| 9 | 5+ with sub-emitters | Mantaflow sim (sim-res 192), 2 variants per sim layer | 8x8 @2048 (Roblox 1024) | R/G/B/A + flowmap | + flowmaps, mesh particles, VFX Graph option, light + shake sync |
| 10 | 5+ synchronized, sub-emitters, secondary sparks/embers off sim | Mantaflow sim (sim-res 256-384, render 2x then downsample), >= 2 variants per sim layer | high-FPS 8x8 64 frames @2048 (Roblox 1024) | R=Alpha, G=Erosion, B=Distortion, A=EmissiveMask | custom Shader Graph / Geometry Nodes / Luau choreography + camera shake/lighting sync; per-layer polish; frame-by-frame timing |
CANONICAL BENCHMARKS (source for SKILL.md STATE_0 calibration): Level 1 / 5 / 10 text lives in SKILL.md <calibration_benchmark>; keep both in sync.
</RUBRIC>

<LEVEL_RESOLUTION>
effective_level = clamp(min(quality, time_budget + 2, token_budget + 2), 1, 10)
tier = T1 if effective_level <= 3 else T2 if effective_level <= 7 else T3
budget_profile = showcase if optimization <= 3 else standard if optimization <= 7 else strict
optimization never changes effective_level.
Examples: (Q10,T5,K9,O2) -> level 7, showcase; (Q4,T1,K1,O9) -> level 3, strict; (Q10,T10,K10,O1) -> level 10, showcase.
</LEVEL_RESOLUTION>

<WORK_CONTRACT>
MANDATORY minimums per effective_level. STATE_4 cannot reach DONE until every column is satisfied (SKILL.md NO_EARLY_EXIT). The time/token columns are the expected cost of doing this work, not targets to pad toward: spend them on the listed items.
| Lvl | Concept variants (STATE_1) | Sim variants per sim layer | Bake tuning iterations per baked layer | Min review loops | Max review loops | Pass threshold (total / every criterion) | Polish passes | LOD versions | Typical time | Est. tokens (all agents) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | — | 0 | 1 (self-check) | 1 | 6.0 / 4 | — | 1 | 5-10 min | 5k-15k |
| 2 | 1 | — | 0 | 1 | 2 | 6.5 / 5 | — | 1 | 10-20 min | 15k-40k |
| 3 | 1 | — | 1 | 1 | 2 | 7.0 / 5 | — | 1 | 15-30 min | 30k-60k |
| 4 | 1 | — | 1 | 2 | 3 | 7.0 / 5 | — | 1 | 20-40 min | 60k-120k |
| 5 | 1 + 1 alt palette | — | 1 | 2 | 4 | 7.0 / 5 | 1 global | 1 | 30-60 min | 100k-200k |
| 6 | 2 | — | 2 | 3 | 5 | 7.5 / 6 | 1 global | 1 | 45-75 min | 150k-300k |
| 7 | 2 | — | 2 | 3 | 6 | 7.5 / 6 | 1 per layer | High + Low | ~1 h | 250k-400k |
| 8 | 2 | 1 (tuned at preview res first) | 2 | 4 | 8 | 8.0 / 7 | 1 per layer | High / Medium / Low | 1-2 h | 400k-700k |
| 9 | 3 | 2, keep best | 3 | 5 | 10 | 8.5 / 7.5 | 2 per layer + timing pass | High / Medium / Low | 2-3 h | 0.7M-1.2M |
| 10 | 3 (user picks at STATE_2) | >= 2, keep best | 3 | 6 | 12 | 9.0 / 8 | 2 per layer + frame-by-frame timing pass + final integration pass | High / Medium / Low + test matrix | 2-4+ h | 1.5M-3M |
DEFINITIONS:
- Concept variant: distinct silhouette/palette/timing proposal with its own blueprint (and concept image when a generator exists). Presented together at STATE_2.
- Sim variant: separate Mantaflow bake with different tuning (platforms/blender_vfx.md <sim_bake> knobs); each scored on C1/C5/C6, best kept, scores logged.
- Bake tuning iteration: preview-resolution bake -> view contact sheet -> adjust knobs. Required before the final-resolution bake.
- Review loop: one full §QUALITY_REVIEW with fresh evidence, followed by fixes for the lowest-scoring criteria.
- Polish pass: targeted refinement of one layer in isolation (solo it, view its frames, fix its weakest criterion), then re-integrate.
- Timing pass: step through the effect at 60 fps frame by frame (or the flipbook cell by cell); fix pops, dead frames, late peaks.
- Integration pass: all layers + light + shake together at gameplay distance against dark and bright backgrounds.
- LOD: High = full quality (never cut for budget). Medium = ~55% particle counts, sub-emitters off, flipbook cell one step down. Low = ~30% counts, <= 3 layers (L1 + L3 + one of L2/L4), 4x4 flipbooks, no distortion/lights.
LONG-RUN RULES (levels >= 7):
- Persist state every loop to the user's project: `vfx_work/<effect>/session_state.yaml`, `manifest.yaml`, `review_log.md` (scores + evidence paths per loop). On context reset or a new session, reload these and resume; never restart from STATE_0.
- Before each long bake (> 5 min), send a one-line progress update with the expected duration.
- If the host cannot run tools for the required time, split work by layer across turns; the contract still applies.
</WORK_CONTRACT>

<QUALITY_REVIEW>
EVIDENCE (capture fresh every loop; never score from the spec or from memory):
| Level | Required evidence |
|---|---|
| 1-4 | Atlas contact sheet of every flipbook over 18% gray; one composite frame at peak |
| 5-7 | + frames at t = -preroll, 0, peak (~0.05T), 0.25T, 0.5T, T |
| 8-10 | + gameplay-distance and close-up views; dark and bright backgrounds; each layer soloed; per-frame energy curve (summed alpha per frame) |
Sources: Blender renders, packer atlases (view the PNG), engine screenshots/recordings (Unity Game view / Recorder; Roblox Studio screenshots). If the agent cannot capture engine views, request them from the user (SKILL.md STATE_4).
CRITERIA (score 0-10 each; total = weighted sum):
| ID | Criterion | Weight | 10 looks like | Common deductions |
|---|---|---|---|---|
| C1 | Silhouette & readability | 0.15 | instantly readable shape at gameplay distance; clear direction | blob, unclear origin, too small/large for gameplay read |
| C2 | Timing & spacing | 0.15 | anticipation reads, peak within 3 frames @60fps, long soft decay | slow attack, linear fades, dead frames, everything ends together |
| C3 | Value hierarchy & contrast | 0.12 | one focal peak (L1), clear falloff, darks support brights | everything equally bright, blown-out white mass, flat mid-gray haze |
| C4 | Color & palette | 0.10 | ramp matches blueprint hex, hue shift hot->cool, no mud | oversaturated, desaturated by tonemapper (AgX), muddy smoke tint |
| C5 | Shape language & detail | 0.12 | layered breakup, multi-scale noise, no visible tiling | uniform noise, soft blobs, repetition, procedural look |
| C6 | Motion quality | 0.12 | continuous motion, physical debris arcs, no boil/jitter | popping, flipbook stutter, frame jitter, floaty sparks |
| C7 | Layer integration | 0.12 | layers read as one event, correct sorting, matched lighting | layers detached, sorting flicker, smoke glowing at night |
| C8 | Technical cleanliness | 0.12 | no halos, no cell bleed, no clipping, soft intersections | dark fringes, hard cell edges, cut-off frames, hard depth intersections |
SCORING DISCIPLINE:
- Every score cites evidence (file path + frame/cell). No evidence => score 0 for that criterion.
- Any score >= 8 must state what would make it 10; that item becomes a candidate fix.
- A score may rise only if the evidence visibly changed since the last loop (no inflation).
- Fix order next loop: lowest weighted gap first (weight x (10 - score)).
OUTPUT per loop: `loop N | C1..C8 scores | total | threshold | pass? | top 3 fixes`, appended to review_log.md at levels >= 7.
</QUALITY_REVIEW>

<OPTIMIZATION_PROFILES>
| Profile | optimization | Unity budget source | Roblox budget source | Enforcement | Version audited (level >= 7 LODs) |
|---|---|---|---|---|---|
| showcase | 1-3 | PC column x 4 | x 3 | report only; never cut quality | none enforced (all LODs reported) |
| standard | 4-7 | PC column x 1 | x 1 | fix only if the fix costs <= 0.5 review score; otherwise report | Medium must PASS; High reported |
| strict | 8-10 | Mobile column x 1 | x 0.5 | enforce; re-score after every cut | Low must PASS; Medium reported |
Levels < 7 ship one version; it is the audited version.
Multipliers apply to counts and memory (draw calls, particles, overdraw, texture MB), not to "texture samples per fragment" or "realtime lights" (use the column value).
BASE BUDGETS (per effect instance, at peak; select row block by tier of effective_level, then apply profile):
UNITY URP:
| Metric | T1 PC | T1 Mobile | T2 PC | T2 Mobile | T3 PC | T3 Mobile |
|---|---|---|---|---|---|---|
| max_draw_calls (layers + light) | 2 | 2 | 6 | 4 | 12 | 6 |
| max_live_particles (Shuriken) | 50 | 30 | 300 | 120 | 2000 | 300 |
| max_live_particles (VFX Graph) | — | — | 5000 | n/a | 50000 | n/a |
| max_overdraw_layers (hotspot) | 3 | 2 | 6 | 4 | 10 | 5 |
| max_texture_memory_mb (incl. mips) | 1 | 0.5 | 6 | 3 | 24 | 8 |
| texture samples per fragment | 1 | 1 | 2 | 2 | 4 | 2 |
| realtime lights | 0 | 0 | 1 | 0-1 | 2 | 1 |
ROBLOX:
| Metric | T1 | T2 | T3 |
|---|---|---|---|
| max_draw_calls (= emitter + beam + trail instances) | 3 | 6 | 12 |
| max_live_particles | 40 | 150 | 400 |
| max_overdraw_layers (hotspot, formula estimate) | 2 | 4 | 6 |
| textures (each <= 1024) | 1 | 3 | 6 |
| PointLights | 0-1 | 1 | 2 |
| largest L1 particle size (studs, relative to 5-stud character) | 6 | 10 | 16 |
| max_texture_memory_mb (engine-managed; count 4 MB per 1024 RGBA) | 1 | 12 | 24 |
BLENDER BAKE (offline cost, not runtime; independent of profile):
| Metric | T1 | T2 | T3 |
|---|---|---|---|
| frames | 4 | 16 | 64 |
| cell px rendered | 128-256 | 256 | 256-512 (render 2x, downsample) |
| EEVEE render samples | 16 | 32 | 64 |
| Mantaflow sim-res | — | — | 128 (L8) / 192 (L9) / 256-384 (L10) |
| GN mesh tris exported per effect mesh | 500 | 1000 | 2000 |
</OPTIMIZATION_PROFILES>

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
Run in STATE_4 against §OPTIMIZATION_PROFILES budgets (tier block x profile). Output `check | budget | actual | PASS/FAIL | fix`.
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
FAIL handling by budget_profile (§OPTIMIZATION_PROFILES): showcase -> report only. standard/strict -> fix the cheapest lever first (count -> size -> lifetime -> resolution -> layer removal) on the audited LOD only, re-score with §QUALITY_REVIEW after each cut; standard reverts any cut costing > 0.5 score. Never remove L1. Never cut the High LOD. Report residual FAILs at max_loops with the reason.
</AUDIT>
