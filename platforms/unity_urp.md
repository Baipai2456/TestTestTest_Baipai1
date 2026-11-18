---
id: platform_unity_urp
platform: unity
engine_versions: ["2022.3 LTS (URP 14)", "Unity 6 / 6000.x (URP 17)"]
pipelines: [Shuriken ParticleSystem, VFX Graph]
load_when: session.platform in [unity, blender->unity]
deliverables: [texture import table, Shader Graph blueprint, particle module configs, VfxSequencer.cs, prefab hierarchy, test procedure]
---

# UNITY URP — SHADER GRAPH + SHURIKEN / VFX GRAPH IMPLEMENTATION SPEC

<project_prerequisites>
| Setting | Location | Value | Why |
|---|---|---|---|
| Depth Texture | URP Asset > Rendering | ON | Soft particles / Depth Fade (Scene Depth node) |
| Opaque Texture | URP Asset > Rendering | ON only if heat-haze refraction layer exists | Scene Color node |
| HDR | URP Asset > Quality | ON | Emission > 1.0 feeds Bloom |
| Bloom | Global Volume > Bloom | Threshold 0.9-1.1, Intensity 0.5-1.5 | HDR core reads as glow |
| Tonemapping | Global Volume | ACES or Neutral (match game) | Predictable HDR roll-off |
| Color Space | Player Settings | Linear | Correct additive math |
| VFX Graph | Package Manager `com.unity.visualeffectgraph` | install only if pipeline=VFX Graph | Compute-capable targets only (no WebGL/older mobile GPUs) |
</project_prerequisites>

<texture_import>
| Texture kind | sRGB | Alpha Source | Alpha Is Transparency | Wrap | Mipmaps | Compression (PC / Mobile) | Max Size |
|---|---|---|---|---|---|---|---|
| Color flipbook (straight RGBA) | ON | Input Texture Alpha | ON | Clamp | ON (Kaiser) | BC7 / ASTC 6x6 | manifest.size_px |
| Packed mask R/G/B (no A) | OFF | None | OFF | Clamp (flipbook) or Repeat (static tile) | ON | BC1 (DXT1) / ASTC 6x6 | manifest.size_px |
| Packed mask R/G/B/A | OFF | Input Texture Alpha | OFF | per use | ON | BC7 / ASTC 6x6 | manifest.size_px |
| Tileable noise (packed G/B) | OFF | None | OFF | Repeat | ON | BC1 / ASTC 8x8 | 256-512 |
| Flowmap (RG vectors) | OFF | None | OFF | Repeat | OFF (or ON with low bias) | BC5 or uncompressed RG / ASTC 4x4 | 256 |
RULES: never enable `Alpha Is Transparency` on data textures (it dilates color into alpha=0 texels, corrupting packed channels). Flipbook padding >= 2 px prevents mip bleed between cells.
</texture_import>

<texture_modes>
| Mode | When | _MainTex | _NoiseTex | Erosion source | Shape source |
|---|---|---|---|---|---|
| PACKED_STATIC | Shape is a single static mask | R=shape, G=erosion, B=distortion, [A=emissive] | optional (extra scrolling detail) | _MainTex.g (per-texel, aligned to shape) | _MainTex.r |
| COLOR_FLIPBOOK | Shape animates via flipbook | straight RGBA atlas | REQUIRED: G=erosion, B=distortion tileable | _NoiseTex.g (scrolling) | _MainTex.a |
Keyword: Boolean Keyword `_COLOR_FLIPBOOK` (Shader Feature, Material scope). Off = PACKED_STATIC.
</texture_modes>

<vertex_streams>
Particle System > Renderer > Custom Vertex Streams = ON. Order is significant; Unity packs streams sequentially into TEXCOORDn.
| # | Stream | Packed into | Shader Graph access |
|---|---|---|---|
| 1 | Position | POSITION.xyz | Position node |
| 2 | Normal | NORMAL.xyz | (only if lit) |
| 3 | Color | COLOR.xyzw | Vertex Color node (rgb tint, a = alpha over life) |
| 4 | UV | TEXCOORD0.xy | UV node (UV0) -> Split R,G |
| 5 | Custom1.xy | TEXCOORD0.zw | UV node (UV0) -> Split B (= Custom1.x), A (= Custom1.y) |
| 6 (L>=8, flipbook blending) | UV2 | TEXCOORD1.xy | UV node (UV1) -> Split R,G |
| 7 (L>=8, flipbook blending) | AnimBlend | TEXCOORD1.z | UV node (UV1) -> Split B |
Custom Data module: Custom1 = Vector, components = 2.
- Custom1.x (erosion progress): Curve over lifetime, keys `(0,0) (0.4,0.1) (1,1)` (slow start, eats out during decay). This IS normalized particle age (`AgePercent`) remapped by an artist curve; per-particle, zero extra material instances.
- Custom1.y (distortion amount): Curve `(0,1) (1,0.2)`.
ALTERNATIVE (no curve control): add stream `Lifetime > AgePercent` instead of Custom1.xy -> lands in TEXCOORD0.z; read UV0.B. Use Custom1 when artists need shaping.
VERIFY: the Renderer module lists each stream with its TEXCOORD target; the Shader Graph channel used MUST equal that label. Mismatch symptom: whole particle dissolved or never dissolving.
</vertex_streams>

<shader_graph name="SG_VFX_Master_Particle">
GRAPH SETTINGS:
| Field | Value |
|---|---|
| Target | Universal (+ "Support VFX Graph" ON if pipeline=VFX Graph) |
| Material | Unlit |
| Allow Material Override | ON |
| Surface Type | Transparent |
| Blending Mode | Additive (fire/energy/sparks) / Alpha (smoke/residual) / Premultiply (mixed) |
| Render Face | Both |
| Depth Write | Force Disabled |
| Depth Test | LEqual |
| Alpha Clipping | OFF (ON + threshold 0.01 only for debris cards needing depth-sorted cutout) |
| Cast Shadows | OFF |
PROPERTIES (Reference names exact):
| Reference | Type | Default | Notes |
|---|---|---|---|
| _MainTex | Texture2D | white | flipbook atlas or packed mask |
| _NoiseTex | Texture2D | gray | tileable, linear, G=erosion B=distortion |
| _NoiseTiling | Vector2 | (1,1) | |
| _NoiseScroll | Vector2 | (0.05,0.25) | UV/s |
| _DistortionStrength | Float (Slider 0-0.3) | 0.06 | multiplied by Custom1.y |
| _ErosionSoftness | Float (Slider 0.01-1) | 0.15 | |
| _EdgeWidth | Float (Slider 0-0.3) | 0.05 | burning edge band |
| _EdgeColor | Color (HDR) | (4,1.6,0.3,1) | |
| _ColorCore | Color (HDR) | (4,3.6,2.8,1) | |
| _ColorEdge | Color (HDR) | (1.6,0.25,0,1) | |
| _Emission | Float | 2 | global HDR multiplier |
| _EmissiveMaskBoost | Float | 0 | >0 only when packed A=EmissiveMask (Level 10) |
| _SoftFade | Float | 0.5 | meters, depth fade distance |
| _COLOR_FLIPBOOK | Boolean Keyword | off | see texture_modes |
NODE GRAPH (deterministic build order; `->` = connection, `Name[Out]` = output port):
```
N01 UV(UV0) -> N02 Split
N03 Vector2(N02.R, N02.G)                                  # base uv
N04 Time[Time] * _NoiseScroll  -> N05 Multiply
N06 TilingAndOffset(UV=N03, Tiling=_NoiseTiling, Offset=N05)
N07 SampleTexture2D(_NoiseTex, UV=N06)                     # noise.g erosion, noise.b distortion
N08 Remap(N07.B, In(0,1), Out(-1,1))
N09 Multiply(N08, _DistortionStrength) -> N10 Multiply(N09, N02.A)   # Custom1.y scales distortion
N11 Add(N03, N10.xx)                                       # distorted uv (Vector2)
N12 SampleTexture2D(_MainTex, UV=N11)
N13 Keyword _COLOR_FLIPBOOK: On=N12.A, Off=N12.R           # shape
N14 Keyword _COLOR_FLIPBOOK: On=N07.G, Off=N12.G           # erosion field
N15 Lerp(A=-_ErosionSoftness, B=1, T=N02.B)                # threshold t (Custom1.x)
N16 Subtract(N14, N15) -> N17 Divide(N16, _ErosionSoftness) -> N18 Saturate   # erosion alpha
N19 Add(N15, _ErosionSoftness) ; N20 Subtract(N14, N19) ; N21 Absolute(N20)
N22 Divide(N21, max(_EdgeWidth,1e-4)) -> N23 OneMinus -> N24 Saturate -> N25 Multiply(N24, N13)  # edge band
N26 Keyword _COLOR_FLIPBOOK: On=Multiply(N12.RGB, _ColorCore), Off=Lerp(_ColorEdge, _ColorCore, N13)
N27 VertexColor -> N28 Multiply(N26, N27.RGB) -> N29 Multiply(N28, _Emission)
N30 Multiply(N12.A, _EmissiveMaskBoost) -> N31 Add(1, N30) -> N32 Multiply(N29, N31)   # Off-mode A=emissive; leave _EmissiveMaskBoost=0 in On-mode
N33 Add(N32, Multiply(_EdgeColor, N25))                    # Fragment.BaseColor
N34 SceneDepth(Eye) ; N35 ScreenPosition(Raw) -> Split.A   # fragment eye depth
N36 Subtract(N34, N35.A) -> Divide(_SoftFade) -> Saturate  # depth fade
N37 Multiply(N13, N18) -> Multiply(N27.A) -> Multiply(N36) -> Saturate   # Fragment.Alpha
OUTPUT: BaseColor=N33, Alpha=N37
```
FORMULAS (canonical; see references/scale_rubric_and_budgets.md §SHADER_MATH):
- t = lerp(-s, 1, age); alpha_erode = saturate((E - t)/s)
- uv' = uv + (D*2-1) * k * custom1.y
- depth_fade = saturate((SceneEyeDepth - FragEyeDepth)/fade)
HEAT HAZE VARIANT (L2 distortion ring, effective_level >= 7): duplicate graph -> Surface Transparent, Blending Alpha; BaseColor = SceneColor(ScreenPosition(Default) + N10*0.02); Alpha = N13 * N18. Requires Opaque Texture ON. Renders after transparents only if placed in a later render queue (+10).
</shader_graph>

<shuriken_layer_configs>
Hierarchy: `VFX_<Effect>` (root, VfxSequencer) -> children `L0_Anticipation`, `L1_CoreBurst`, `L2_SecondaryMotion`, `L3_DebrisSparks`, `L4_LingeringResidual`, `FX_Light` (Point Light). Every child ParticleSystem: Play On Awake OFF, Looping OFF, Simulation Space = manifest.coordinate_space, Scaling Mode = Hierarchy, Stop Action = None (root sequencer owns lifetime).
| Module | L0 Anticipation | L1 CoreBurst | L2 SecondaryMotion (ring) | L3 DebrisSparks | L4 Residual smoke |
|---|---|---|---|---|---|
| Duration | preroll_s | 0.1 | 0.1 | 0.1 | 0.3 |
| Start Lifetime | 0.2-0.25 | 0.5-0.7 | 0.4-0.5 | 0.4-0.9 | 1.0-1.6 |
| Start Speed | 0 | 0 | 0 | 12-25 | 0.5-2 |
| Start Size | 1.5-2.0 | 2.5-3.5 | 0.5 | 0.05-0.12 | 1.5-2.5 |
| Start Rotation | 0-360 | 0-360 | 0 | 0 | 0-360 |
| Emission | Rate 60/s | Burst t0: 2-3 | Burst t0: 1 | Burst t0: 20-40 | Burst t0: 4-8 |
| Shape | Sphere r=2.0, Radius Thickness 0 (surface), Velocity over Lifetime Radial = -8 (inward pull) | Sphere r=0.1 | none (Align To Direction off) | Hemisphere/Sphere r=0.2 | Sphere r=0.6 |
| Size over Lifetime | 1 -> 0.2 | 0.6 ->(0.15) 1 -> 1.2 | 0.1 -> 1 (ease-out) | 1 -> 0 | 0.8 -> 1.6 |
| Color over Lifetime alpha | 0, 0.6@0.3, 0 | 0, 1@0.05, 0.6@0.7, 0 | 1, 0 | 1, 1@0.8, 0 | 1, 0.7@0.6, 0 |
| Limit Velocity / Drag | — | — | — | Drag 4-6 | Drag 1 |
| Gravity Modifier | 0 | 0 | 0 | 1.5-3 | -0.05 |
| Noise module | — | — | — | Strength 0.5, Freq 2 (L>=5) | Strength 0.3, Freq 0.5 |
| Texture Sheet Animation | — | Grid NxN, Whole Sheet, Frame over Time linear 0->N²-1, Cycles 1 | — | — | Grid NxN, Start Frame random 0-3 (L>=5) |
| Custom Data Custom1.xy | — | erosion/distortion curves | erosion (0,0)->(1,1) | — | erosion (0,0)(0.5,0.2)(1,1) |
| Renderer Render Mode | Billboard | Billboard | Horizontal Billboard (ground) or Mesh (baked ring) | Stretched Billboard (Speed Scale 0.03-0.06) | Billboard |
| Renderer Sorting Fudge | 0 | -10 (draw last) | -5 | 0 | +10 (draw first) |
| Material blend | Additive | Additive | Additive | Additive | Alpha |
| Max Particles | 20 | 4 | 2 | 40 | 10 |
NOTE: In Unity, lower Sorting Fudge renders later (in front). Map manifest.render_order: highest render_order -> lowest fudge.
SOFT PARTICLES: handled in shader (N34-N36). Do not also enable the legacy Soft Particles quality toggle.
MESH RENDER (L2 baked Blender ring, L>=8): Renderer Mode = Mesh, mesh = imported ring FBX, Render Alignment = Local, Custom1.x drives erosion along UV.y.
</shuriken_layer_configs>

<vfx_graph_mapping>
Use when effective_level >= 7 AND the target supports compute shaders, or particle counts > 2k.
| Shuriken concept | VFX Graph equivalent |
|---|---|
| Burst | Spawn context: Single Burst (Count, Delay = layer.start_s + preroll) |
| Start Lifetime/Size/Speed | Initialize Particle: Set Lifetime Random (Uniform), Set Size, Set Velocity Random |
| Size/Color over Life | Update/Output: Set Size over Life, Set Color over Life (Gradient, HDR) |
| Custom1.x erosion | Output: Shader Graph property `ErosionProgress` <- operator `Age Over Lifetime` (-> Sample Curve) |
| Texture Sheet | Output Particle Quad: UV Mode = Flipbook (Flip Book Size = N,N), Set Tex Index over Life (0 -> N²-1) |
| Stretched Billboard | Output Particle Quad, Orient: Along Velocity |
| Drag/Gravity | Update: Linear Drag, Gravity |
| Soft particles | Output: Soft Particle Fade Distance (built-in) OR shader N34-N36 |
Expose `Spawn` event; drive from VfxSequencer by `visualEffect.SendEvent("OnPlay")` (requires `UnityEngine.VFX`). Keep one Visual Effect asset per effect with one system per layer.
</vfx_graph_mapping>

<control_script file="Assets/VFX/Scripts/VfxSequencer.cs">
Compiles against UnityEngine.CoreModule + ParticleSystemModule (verified on 6000.3). Attach to `VFX_<Effect>` root.
```csharp
// VfxSequencer.cs - layered VFX choreography for URP (Unity 2022.3 LTS / Unity 6).
// Plays L0..L4 ParticleSystems with per-layer offsets, drives a flash light, and applies camera shake.
using System;
using System.Collections;
using UnityEngine;

[DisallowMultipleComponent]
public class VfxSequencer : MonoBehaviour
{
    [Serializable]
    public class Layer
    {
        public string id = "L1_CoreBurst";
        public ParticleSystem system;
        [Tooltip("Seconds relative to impact (t=0). L0 uses negative values.")]
        public float startTime;
        [Tooltip("> 0 overrides authored bursts with a single Emit(count). 0 = Play() authored modules.")]
        public int emitCount;
    }

    [Header("Layers (L0..L4)")]
    public Layer[] layers = Array.Empty<Layer>();

    [Header("Flash Light")]
    public Light flashLight;
    [ColorUsage(false, true)] public Color lightColor = new Color(1f, 0.54f, 0.12f);
    public float lightPeakIntensity = 6f;
    public AnimationCurve lightCurve = new AnimationCurve(
        new Keyframe(0f, 0f, 0f, 40f), new Keyframe(0.05f, 1f), new Keyframe(0.6f, 0f));

    [Header("Camera Shake")]
    public Transform shakeTarget;               // camera or camera rig child; leave null to disable
    public float shakeAmplitude = 0.15f;        // meters
    public float shakeFrequency = 18f;          // Hz
    public float shakeDuration = 0.3f;

    [Header("Lifecycle")]
    public bool playOnEnable = true;
    public bool destroyWhenFinished = true;

    float _preroll;
    Coroutine _running;

    void OnEnable()
    {
        if (flashLight != null) flashLight.intensity = 0f;
        foreach (var l in layers)
        {
            if (l.system == null) continue;
            var main = l.system.main;
            main.playOnAwake = false;
            l.system.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        }
        if (playOnEnable) Play();
    }

    void OnDisable()
    {
        if (_running != null) StopCoroutine(_running);
        _running = null;
    }

    public void Play()
    {
        if (_running != null) StopCoroutine(_running);
        _running = StartCoroutine(Run());
    }

    IEnumerator Run()
    {
        _preroll = 0f;
        foreach (var l in layers) _preroll = Mathf.Max(_preroll, -l.startTime);
        float end = 0f;
        foreach (var l in layers)
        {
            if (l.system == null) continue;
            float life = l.system.main.duration + l.system.main.startLifetime.constantMax;
            end = Mathf.Max(end, l.startTime + life);
            StartCoroutine(PlayLayer(l, l.startTime + _preroll));
        }
        float lightEnd = lightCurve.length > 0 ? lightCurve[lightCurve.length - 1].time : 0f;
        end = Mathf.Max(end, lightEnd, shakeDuration);

        yield return new WaitForSeconds(_preroll);           // impact t = 0
        float t = 0f;
        Vector3 basePos = shakeTarget != null ? shakeTarget.localPosition : Vector3.zero;
        float seed = UnityEngine.Random.value * 100f;
        while (t <= end)
        {
            if (flashLight != null)
            {
                flashLight.color = lightColor;
                flashLight.intensity = lightPeakIntensity * Mathf.Max(0f, lightCurve.Evaluate(t));
            }
            if (shakeTarget != null && t <= shakeDuration)
            {
                float decay = 1f - t / shakeDuration;
                decay *= decay;                               // fast attack, quadratic decay
                float ft = t * shakeFrequency;
                shakeTarget.localPosition = basePos + shakeAmplitude * decay * new Vector3(
                    Mathf.PerlinNoise(seed, ft) * 2f - 1f,
                    Mathf.PerlinNoise(seed + 17.3f, ft) * 2f - 1f,
                    0f);
            }
            else if (shakeTarget != null)
            {
                shakeTarget.localPosition = basePos;
            }
            t += Time.deltaTime;
            yield return null;
        }
        if (flashLight != null) flashLight.intensity = 0f;
        if (shakeTarget != null) shakeTarget.localPosition = basePos;
        _running = null;
        if (destroyWhenFinished) Destroy(gameObject);
    }

    static IEnumerator PlayLayer(Layer l, float delay)
    {
        if (delay > 0f) yield return new WaitForSeconds(delay);
        if (l.emitCount > 0) l.system.Emit(l.emitCount);
        else l.system.Play(true);
    }
}
```
USAGE: spawn prefab at impact point minus preroll lead time when L0 exists (the sequencer delays all layers so L0 starts immediately and L1 fires at preroll). For pooled use set destroyWhenFinished=false and call Play().
CAMERA SHAKE: assign `shakeTarget` to a dedicated child transform under the camera (never the Cinemachine-driven camera itself). With Cinemachine, replace shake block by `CinemachineImpulseSource.GenerateImpulse()` and leave shakeTarget null.
</control_script>

<build_steps>
1. Import textures; apply <texture_import> row per manifest kind.
2. Create SG_VFX_Master_Particle per <shader_graph>; create one Material per blend mode (M_VFX_Additive, M_VFX_Alpha); per-layer looks via Material Property overrides only when unavoidable (each variant = extra batch).
3. Build hierarchy + modules per <shuriken_layer_configs>; set Custom Vertex Streams per <vertex_streams> on every layer using erosion/distortion.
4. Add VfxSequencer to root; fill layers[] with startTime from manifest.layers[].start_s; set light/shake from manifest.extras.
5. Save as prefab `Assets/VFX/Prefabs/VFX_<Effect>.prefab`.
</build_steps>

<test_procedure>
T1 Frame Debugger: count draw calls of the effect at peak (t = 0.05 s); compare to budgets.max_draw_calls.
T2 Scene view > Overdraw mode (or Rendering Debugger > Overdraw in URP 14+): peak hotspot layers <= budgets.max_overdraw_layers.
T3 Particle System > Show bounds; Profiler > Rendering: live particle count at peak <= budgets.max_live_particles.
T4 Dissolve check: set Custom1.x curve constant 0.5 -> particle half-eroded; if fully opaque or invisible, stream/channel mismatch (<vertex_streams> VERIFY).
T5 Soft particle check: place effect intersecting a plane; no hard intersection line.
T6 Timing check: record at 60 fps (Recorder package); L1 peak within 3 frames of impact; L4 last visible frame <= duration_s + max lifetime.
</test_procedure>

<pitfalls>
- Additive + Bloom with BaseColor < 1.0 never blooms: scale _Emission so the L1 core exceeds threshold; keep L3/L4 under threshold to protect value hierarchy.
- Texture Sheet Animation + UV distortion: distortion offsets can sample neighboring cells; keep _DistortionStrength * custom1.y <= padding_px / cell_px, or increase --padding.
- Particle GPU Instancing applies only to Renderer Mode = Mesh with an instancing-capable shader; billboard particles batch per ParticleSystem renderer + material. Every extra material/variant = extra draw call; keep material count minimal.
- Stretched Billboard sparks need Speed Scale tuned to start speed; length = speed * speedScale.
- `Alpha Is Transparency` on packed masks = corrupted G/B near transparent texels.
</pitfalls>
