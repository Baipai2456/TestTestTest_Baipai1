---
id: vfx_architect_schema
role: VFX Lead Architect (high-reasoning model)
used_in: [STATE_1, STATE_3]
outputs: [BLUEPRINT, MANIFEST, HANDOFF]
format: YAML (JSON-equivalent; keys snake_case; no comments in emitted instances)
---

# VFX ARCHITECT — BLUEPRINT, MANIFEST, HANDOFF SPECIFICATION

<architect_directives>
- Reason top-down: gameplay read (what/where/when) -> silhouette -> timing -> layers -> textures -> engine mapping.
- Every numeric value must be explicit (no "about", no ranges without a chosen value) unless the field type is a range.
- Time unit: seconds (float). Size unit: platform native (Unity meters, Roblox studs, Blender meters). Colors: sRGB hex `#RRGGBB`; HDR intensity separate float.
- Prefer fewer, better-timed layers over more particles. Each layer must justify its draw call.
- Reuse one texture across layers via channel packing / flipbook where the target platform allows (Unity, Blender). Roblox: one RGBA texture per visual look; reuse via Color/Size/Transparency variation.
- Value hierarchy: exactly one layer owns peak brightness (L1). All others <= 60% of L1 peak luminance unless effective_level >= 8 and justified.
</architect_directives>

<BLUEPRINT>
Emitted in STATE_1. Schema:
```yaml
blueprint:
  effect_name: string            # PascalCase, e.g. FireballImpact
  gameplay_read: string          # one sentence: what the player must understand
  source: reference | generated_concept
  dominant_silhouette:
    shape: radial_burst | cone | arc_slash | column | ring | sphere | beam | spiral | custom
    aspect: float                # width/height at peak
    notes: string
  color_ramp:                    # >=3 stops, ordered hot->cool
    - {stop: core, hex: "#FFF4D6", hdr_intensity: 4.0}
    - {stop: mid, hex: "#FF8A1F", hdr_intensity: 2.0}
    - {stop: edge, hex: "#7A1400", hdr_intensity: 1.0}
    - {stop: residual, hex: "#2B2B2B", hdr_intensity: 0.0}
  motion_timing:
    duration_s: float            # T, excluding L0 pre-roll
    preroll_s: float             # L0 length, 0 if absent
    attack_s: float              # 0 -> peak
    decay_curve: ease_out_cubic | ease_out_expo | linear | custom
    hit_stop_frame: bool         # freeze-frame hint for gameplay
  emitter_layers:                # exactly 5 entries L0..L4
    - {id: L0_Anticipation, status: present | absent, description: string, inferred: bool}
  required_2d_maps:
    - {name: string, kind: flipbook | noise | mask | gradient | flowmap, grid: "4x4" | null, cell_px: int | null, tileable: bool}
  platform_feasibility: [string] # constraints that change the design on the chosen platform
  effective_level: int
```
</BLUEPRINT>

<MANIFEST_SCHEMA>
Emitted in STATE_3 STEP 1. The manifest is the single source of truth for SA1/SA2/SA3.
```yaml
manifest:
  manifest_id: string            # <effect_name>_v<int>, increments on every revision
  effect_name: string
  platform: unity | roblox | blender | blender->unity | blender->roblox
  effective_level: int           # 1..10
  optimization: int              # 1..10 (user answer, STATE_0)
  budget_profile: showcase | standard | strict
  duration_s: float
  preroll_s: float
  coordinate_space: local | world
  scale_reference: string        # e.g. "character height = 1.8 m" | "character height = 5 studs"
  color_ramp: [{hex: string, hdr_intensity: float}]
  textures:
    - id: string                 # T_<Effect>_<Purpose>, e.g. T_Fireball_CoreFlip
      kind: flipbook | packed_mask | noise | gradient | flowmap | color_sprite
      source: generate | procedural | blender_bake | blender_sim | user_supplied   # blender_sim = Mantaflow (platforms/blender_vfx.md <sim_bake>)
      color_space: srgb | linear
      tileable: bool
      size_px: int               # final atlas/texture size, power of two
      flipbook: {grid: 2 | 4 | 8, cell_px: int, frames_source: int, fps: float, mode: loop | oneshot | pingpong | random} | null
      channels: {r: string, g: string, b: string, a: string} | null   # semantic per channel or "unused"
      pipeline:                  # ordered packer invocations (argv after script path)
        - [extract-alpha, <in>, <out>, --mode, max]
        - [stitch-flipbook, <in_dir>, <out.png>, --grid, 4x4, --max-size, 1024, --padding, 2, --meta, <meta.json>]
  layers:
    - id: L0_Anticipation | L1_CoreBurst | L2_SecondaryMotion | L3_DebrisSparks | L4_LingeringResidual
      enabled: bool
      start_s: float             # relative to impact t=0; L0 negative
      duration_s: float
      emission: {type: burst | rate | distance, count: int, rate_per_s: float}
      lifetime_s: [float, float] # min, max
      start_size: [float, float]
      start_speed: [float, float]
      size_over_life: string     # curve keyword or keypoints "0:0.3,0.1:1,1:1.4"
      alpha_over_life: string
      color_over_life: string    # hex keypoints "0:#FFF4D6,0.3:#FF8A1F,1:#7A1400"
      blend: additive | alpha | premultiplied
      texture_id: string
      shader_features: [erosion, uv_distortion, soft_particle, edge_glow, fresnel, flipbook_blend]
      render_order: int          # higher draws later/on top; maps to Unity sortingFudge/Order in Layer, Roblox ZOffset
      max_particles: int
      platform_overrides: {}     # free-form, platform-file keys only
  extras:
    light: {enabled: bool, color_hex: string, peak_intensity: float, range: float, attack_s: float, decay_s: float}
    camera_shake: {enabled: bool, amplitude: float, frequency_hz: float, duration_s: float}
    audio_cue_s: float | null
  lods:                          # required when effective_level >= 7 (High/Medium/Low); [] otherwise
    - id: high | medium | low
      particle_scale: float      # multiplier on every layer max_particles/emission count (high = 1.0)
      disabled_layers: [string]  # layer ids removed in this LOD
      texture_overrides: {}      # texture_id -> {size_px: int, grid: int}
  budgets:                       # references/scale_rubric_and_budgets.md §OPTIMIZATION_PROFILES: tier block x budget_profile
    max_draw_calls: int
    max_live_particles: int
    max_texture_memory_mb: float
    max_overdraw_layers: int
```
</MANIFEST_SCHEMA>

<VALIDATION_RULES>
V01 platform in {unity, roblox, blender, blender->unity, blender->roblox}.
V02 every texture.size_px is power of two; roblox|blender->roblox => size_px <= 1024.
V03 flipbook.grid in {2,4,8}; flipbook.cell_px * grid == size_px.
V04 roblox: no texture.kind == packed_mask referenced by a layer (packed masks are unusable without custom shaders). Flowmaps/noise only as baked RGBA looks.
V05 linear color_space for kind in {packed_mask, noise, flowmap}; srgb for color_sprite, color flipbook.
V06 exactly one layer has the maximum hdr peak (L1_CoreBurst). L1 enabled always.
V07 layer count satisfies SKILL.md <layer_model> RULES for effective_level.
V08 L0 start_s < 0 when enabled; all other start_s >= 0.
V09 sum over layers of max_particles (x audited LOD particle_scale) <= budgets.max_live_particles. showcase: warning only.
V10 count of enabled layers in the audited LOD + light (if enabled) <= budgets.max_draw_calls. showcase: warning only.
V11 every layer.texture_id resolves to textures[].id.
V12 alpha_over_life ends at 0 for every layer (no pop-out). size/alpha keypoints t sorted in [0,1].
V13 render_order unique per layer; L4 lowest (behind), L1 highest unless design states otherwise.
V14 flipbook.frames_source >= grid^2 OR pipeline uses --frame-policy even with --pad-mode hold.
V15 effective_level >= 8: every fire/smoke/explosion flipbook has source blender_sim (procedural shader bakes are levels 1-7 only).
V16 effective_level >= 7: lods contains high, medium (level >= 8) and low; high has particle_scale 1.0 and no disabled_layers; low keeps L1.
V17 budget_profile matches optimization (1-3 showcase, 4-7 standard, 8-10 strict); budgets = tier block x profile, checked against the audited LOD.
On failure: list failing rule IDs, auto-fix, re-validate. Report fixes in one line each.
</VALIDATION_RULES>

<HANDOFF>
Every sub-agent ends its output with:
```yaml
handoff:
  agent: SA1 | SA2 | SA3
  manifest_id: string
  status: complete | partial | blocked
  produced: [{path: string, kind: string, size_px: int | null, sha256_8: string | null}]
  consumed: [string]
  deviations: [{field: string, manifest_value: any, actual_value: any, reason: string}]
  unverified: [string]           # anything not executed/tested
  next: string                   # the next agent or STATE
```
Architect merges handoffs; any `deviations` entry forces manifest_id increment and re-validation.
</HANDOFF>

<EXAMPLE_MANIFEST level="6" platform="roblox">
```yaml
manifest:
  manifest_id: FireballImpact_v1
  effect_name: FireballImpact
  platform: roblox
  effective_level: 6
  optimization: 5
  budget_profile: standard
  duration_s: 1.2
  preroll_s: 0.25
  coordinate_space: world
  scale_reference: "character height = 5 studs"
  color_ramp:
    - {hex: "#FFF4D6", hdr_intensity: 4.0}
    - {hex: "#FF8A1F", hdr_intensity: 2.0}
    - {hex: "#7A1400", hdr_intensity: 1.0}
    - {hex: "#2B2B2B", hdr_intensity: 0.0}
  textures:
    - id: T_Fireball_CoreFlip
      kind: flipbook
      source: blender_bake
      color_space: srgb
      tileable: false
      size_px: 1024
      flipbook: {grid: 4, cell_px: 256, frames_source: 16, fps: 24, mode: oneshot}
      channels: null
      pipeline:
        - [extract-alpha, frames/core, alpha/core, --mode, max, --white-rgb]
        - [stitch-flipbook, alpha/core, out/T_Fireball_CoreFlip.png, --grid, 4x4, --max-size, 1024, --padding, 2, --meta, out/T_Fireball_CoreFlip.json]
    - id: T_Fireball_Spark
      kind: color_sprite
      source: procedural
      color_space: srgb
      tileable: false
      size_px: 128
      flipbook: null
      channels: null
      pipeline: []
    - id: T_Fireball_Smoke
      kind: flipbook
      source: blender_bake
      color_space: srgb
      tileable: false
      size_px: 1024
      flipbook: {grid: 4, cell_px: 256, frames_source: 16, fps: 12, mode: oneshot}
      channels: null
      pipeline:
        - [stitch-flipbook, frames/smoke, out/T_Fireball_Smoke.png, --grid, 4x4, --max-size, 1024, --padding, 2]
    - id: T_Fireball_Ring
      kind: color_sprite
      source: blender_bake
      color_space: srgb
      tileable: false
      size_px: 512
      flipbook: null
      channels: null
      pipeline:
        - [extract-alpha, frames/ring/frame_0008.png, out/T_Fireball_Ring.png, --mode, max, --white-rgb]
  layers:
    - {id: L0_Anticipation, enabled: true, start_s: -0.25, duration_s: 0.25, emission: {type: rate, count: 0, rate_per_s: 60}, lifetime_s: [0.2, 0.25], start_size: [1.5, 2.0], start_speed: [0, 0], size_over_life: "0:1,1:0.2", alpha_over_life: "0:0,0.3:0.6,1:0", color_over_life: "0:#FF8A1F,1:#FFF4D6", blend: additive, texture_id: T_Fireball_Spark, shader_features: [], render_order: 3, max_particles: 15, platform_overrides: {ShapeInOut: Inward, Shape: Sphere}}
    - {id: L1_CoreBurst, enabled: true, start_s: 0.0, duration_s: 0.4, emission: {type: burst, count: 3, rate_per_s: 0}, lifetime_s: [0.6, 0.7], start_size: [4, 5], start_speed: [0, 0], size_over_life: "0:0.6,0.15:1,1:1.2", alpha_over_life: "0:0,0.05:1,0.7:0.6,1:0", color_over_life: "0:#FFF4D6,0.4:#FF8A1F,1:#7A1400", blend: additive, texture_id: T_Fireball_CoreFlip, shader_features: [], render_order: 5, max_particles: 3, platform_overrides: {Brightness: 4, FlipbookMode: OneShot}}
    - {id: L2_SecondaryMotion, enabled: true, start_s: 0.02, duration_s: 0.45, emission: {type: burst, count: 1, rate_per_s: 0}, lifetime_s: [0.45, 0.45], start_size: [1, 1], start_speed: [0.01, 0.01], size_over_life: "0:1,1:9", alpha_over_life: "0:0.9,0.1:1,1:0", color_over_life: "0:#FFF4D6,1:#FF8A1F", blend: additive, texture_id: T_Fireball_Ring, shader_features: [], render_order: 4, max_particles: 1, platform_overrides: {Orientation: VelocityPerpendicular}}
    - {id: L3_DebrisSparks, enabled: true, start_s: 0.03, duration_s: 0.1, emission: {type: burst, count: 30, rate_per_s: 0}, lifetime_s: [0.4, 0.8], start_size: [0.15, 0.3], start_speed: [25, 45], size_over_life: "0:1,1:0", alpha_over_life: "0:1,0.8:1,1:0", color_over_life: "0:#FFF4D6,1:#FF8A1F", blend: additive, texture_id: T_Fireball_Spark, shader_features: [], render_order: 2, max_particles: 30, platform_overrides: {Drag: 6, Acceleration: "0,-30,0", Orientation: VelocityParallel}}
    - {id: L4_LingeringResidual, enabled: true, start_s: 0.1, duration_s: 0.2, emission: {type: burst, count: 6, rate_per_s: 0}, lifetime_s: [1.0, 1.4], start_size: [3, 4], start_speed: [2, 5], size_over_life: "0:0.8,1:1.6", alpha_over_life: "0:1,0.6:0.7,1:0", color_over_life: "0:#2B2B2B,1:#2B2B2B", blend: alpha, texture_id: T_Fireball_Smoke, shader_features: [], render_order: 1, max_particles: 6, platform_overrides: {LightInfluence: 1, LightEmission: 0}}
  extras:
    light: {enabled: true, color_hex: "#FF8A1F", peak_intensity: 6, range: 16, attack_s: 0.03, decay_s: 0.5}
    camera_shake: {enabled: true, amplitude: 0.35, frequency_hz: 18, duration_s: 0.3}
    audio_cue_s: 0.0
  lods: []
  budgets: {max_draw_calls: 6, max_live_particles: 150, max_texture_memory_mb: 12, max_overdraw_layers: 4}
```
NOTE (Roblox, V10): Beam/Trail/ParticleEmitter instances are batched by the engine differently from Unity draw calls; max_draw_calls is interpreted as "max distinct emitter/beam/trail instances" on roblox.
</EXAMPLE_MANIFEST>
