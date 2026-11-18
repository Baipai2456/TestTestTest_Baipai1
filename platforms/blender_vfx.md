---
id: platform_blender_vfx
platform: blender
blender_versions: ["4.2 LTS", "4.5 LTS", "5.x (bake script verified on 5.2)"]
load_when: session.platform in [blender, blender->unity, blender->roblox]
deliverables: [shader node blueprint, geometry nodes blueprints, bake script, packer commands, export settings, test procedure]
---

# BLENDER — SHADER NODES + GEOMETRY NODES + COMPOSITOR + ORTHOGRAPHIC FLIPBOOK BAKE SPEC

<version_matrix>
| Topic | <= 4.1 | 4.2 - 4.5 | 5.x |
|---|---|---|---|
| EEVEE engine id | `BLENDER_EEVEE` | `BLENDER_EEVEE_NEXT` | `BLENDER_EEVEE` (select by enum lookup, never hardcode) |
| Material transparency | `blend_method` = CLIP / HASHED / BLEND | `surface_render_method` = DITHERED (replaces Hashed/Clip) / BLENDED | same as 4.2 |
| Alpha Clip equivalent | `blend_method='CLIP'` + `alpha_threshold` | DITHERED + Math GREATER_THAN on alpha before shader mix | same |
| Node group sockets | `ng.inputs.new` | `ng.interface.new_socket` | same |
| Animation F-curves | `action.fcurves` | `action.fcurves` (layered actions from 4.4) | layered: `action.layers[].strips[].channelbags[].fcurves` |
| `use_nodes` (material/world) | required | required | deprecated (node trees exist by default); guard with `node_tree is None` |
| Compositor tree | `scene.node_tree` (after `scene.use_nodes=True`) | same | `scene.compositing_node_group` (node group assigned to scene) |
Rule: always feature-detect (`hasattr`, enum lookup). The bake script below does.
</version_matrix>

<shader_node_blueprint name="M_VFX_Bake">
Purpose: render-time look for flipbook bakes AND in-Blender real-time preview. Emission-only (no lighting dependency).
```
TexCoord.UV ─┬─> NoiseTex(4D, Scale 4, Detail 6, W=animated) .Color -> VMath SUBTRACT(0.5) -> VMath SCALE(k=animated 0.05->0.35)
             └─> VMath ADD (uv + offset) = distorted_uv
distorted_uv -> SHAPE:
   radial: VMath SUBTRACT(0.5,0.5,0) -> VMath LENGTH -> MapRange(0.5 -> 0.0 => 0 -> 1)
   band (rings/trails): SeparateXYZ.Y -> Math MULTIPLY(pi) -> Math SINE
TexCoord.UV -> NoiseTex(Scale 7).Fac -> MapRange(From Min = t, From Max = t + s, clamp) = erosion       # t animated 0 -> 0.72
shape * erosion (Math MULTIPLY, clamp) = alpha
alpha -> ColorRamp(cool #7A1400 @0, mid #FF8A1F @0.55, hot #FFF4D6 @1) -> Emission.Color ; Emission.Strength animated (1 -> 4 @15% -> 0.6)
MixShader(Fac=alpha, 1=TransparentBSDF, 2=Emission) -> MaterialOutput.Surface
```
VARIANTS:
| Need | Node change |
|---|---|
| Voronoi cracks erosion | replace erosion NoiseTex with VoronoiTex (F1, Euclidean) `.Distance` |
| Hard stylized edge | MapRange interpolation STEPPED (steps 3-4) or narrow From range (s=0.02) |
| Burn edge color | second MapRange (t+s .. t+2s) -> mix toward hot color |
| Alpha Clip look (4.2+) | Math GREATER_THAN(alpha, 0.5) -> Mix Fac; render method DITHERED |
| Fresnel rim (3D shells) | LayerWeight.Facing -> Math POWER(2) -> multiply emission |
ColorRamp colors are scene-linear: convert sRGB hex via `c<=0.04045 ? c/12.92 : ((c+0.055)/1.055)^2.4` (done in script).
Color management for bakes: View Transform = Standard, Look = None (AgX/Filmic desaturate authored ramps).
</shader_node_blueprint>

<geometry_nodes_blueprints>
<gn name="GN_ShockRing" status="implemented in bake script">
Grid(1x1, 97x3 verts) -> StoreNamedAttribute(FLOAT2, CORNER, "UVMap" = Grid.UV Map) -> SetPosition(polar warp) -> MergeByDistance(1e-4) -> SetMaterial
polar warp: angle = x*2pi + pi ; r = radius(t) + y*Width ; pos = (cos(angle)*r, sin(angle)*r, 0)
radius(t) = MapRange(ease, RadiusStart, RadiusEnd); ease = 1-(1-t)^3; t = saturate((SceneTime.Frame-1)/DurationFrames)
UV: U = around ring (scroll for flow), V = across band (sin(pi*V) falloff).
Export for engines: apply modifier at a mid frame (or keep GN for bake-only); ring mesh UVs drive Unity Mesh-render erosion along V.
</gn>
<gn name="GN_MeshTrail">
Input: curve object (path of weapon tip / projectile). Nodes:
ObjectInfo(path curve).Geometry -> ResampleCurve(Count 64) -> SetCurveRadius(SplineParameter.Factor -> FloatCurve taper 1->0)
-> CurveToMesh(Profile = CurveLine (-0.5,0,0)->(0.5,0,0), Fill Caps off)
UV: StoreNamedAttribute(FLOAT2, CORNER, "UVMap") with U = SplineParameter.Factor (captured on curve via CaptureAttribute before CurveToMesh), V = profile parameter.
Trim over time: DeleteGeometry(Selection = SplineParameter.Factor > SceneTime-driven head) or TrimCurve(Factor start/end animated).
Use: bake slash arcs as mesh for Unity (Mesh render mode, erosion along U) or render to flipbook for Roblox.
</gn>
<gn name="GN_Debris">
Points: DistributePointsOnFaces(IcoSphere r=0.1, Density high) OR Points(Count N).
InstanceOnPoints(Instance = CollectionInfo(shard meshes) | IcoSphere subdiv 1, Pick Instance on, Rotation = RandomValue(VECTOR 0..2pi), Scale = RandomValue(0.3..1))
Ballistic motion: SetPosition(Offset = dir * speed * t + (0,0,-0.5*g*t^2)); dir = normalize(Position) + RandomValue(-0.3..0.3); t = SceneTime.Seconds.
ScaleInstances(scale *= 1 - t/life) ; RealizeInstances before export.
Use: L3 shards baked to flipbook (Roblox) or exported as mesh particles (Unity Mesh render mode, Random mesh per particle).
</gn>
</geometry_nodes_blueprints>

<compositor>
Preview only (bakes must stay un-bloomed; engines add bloom):
| Node | Setting | Purpose |
|---|---|---|
| Glare | type Bloom (4.2+) or Fog Glow; threshold 1.0; size 6-8 | preview HDR glow |
| Alpha Over | background 18% gray | judge alpha edges |
Exception: platform=roblox AND Lighting.Bloom unavailable in target experience -> bake a mild Glare into L1 frames (Glare threshold 1.0, mix -0.5) and record it in manifest deviations.
5.x API: create a compositor node group and assign `scene.compositing_node_group`; <= 4.x: `scene.use_nodes = True; scene.node_tree`.
</compositor>

<ortho_bake_rules>
| Rule | Value |
|---|---|
| Camera | Orthographic, ortho_scale 2.0, looking -Z at XY plane, effect centered at origin |
| Safe area | effect max extent <= 0.95 of half-frame on every frame (packer padding + mip bleed) |
| Resolution | = target cell_px (128/256/512); render at 2x and let packer downsample for anti-aliasing at L>=8 |
| Frames | = grid^2 (4/16/64) for 1:1 mapping; or render more and let `stitch-flipbook --frame-policy even` resample |
| Mode additive | Black world, film_transparent OFF, RGB PNG -> `extract-alpha` (fire, energy, sparks) |
| Mode alpha | film_transparent ON, RGBA PNG (smoke, dust, dark residual) -> stitch directly |
| Color depth | 8-bit PNG for engine; 16-bit only for intermediate data maps |
| Tileable noise | do not bake in Blender; use agents/asset_subagent_prompts.md §PROCEDURAL_FALLBACK (exact periodicity) |
| Flowmap | Emission = (flow.xy * 0.5 + 0.5, 0) from Vector Math on a Tangent/Vector field; Non-Color; film transparent OFF; 16-bit PNG; Unity import sRGB OFF |
</ortho_bake_rules>

<bake_script file="tools/vfx_bake_blender.py (write to the user's project when needed)">
Headless: `blender -b --factory-startup -P vfx_bake_blender.py -- --out <dir> --effect burst|ring --frames 16 --res 256 --mode additive|alpha [--color-hot FFF4D6 --color-mid FF8A1F --color-cool 7A1400 --seed 0]`
Outputs `<dir>/frame_0001.png ...`. Verified on Blender 5.2: 16-frame burst and ring bakes stitched into 4x4 atlases with readable attack/decay.
```python
# vfx_bake_blender.py - headless orthographic flipbook bake (Blender 4.2 LTS .. 5.x)
# usage: blender -b --factory-startup -P vfx_bake_blender.py -- --out ./frames --effect burst --frames 16 --res 256 --mode additive
import argparse
import math
import sys
from pathlib import Path

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--effect", choices=["burst", "ring"], default="burst")
ap.add_argument("--frames", type=int, default=16)          # = grid*grid (4, 16, 64)
ap.add_argument("--res", type=int, default=256)            # = cell px; power of two
ap.add_argument("--mode", choices=["additive", "alpha"], default="additive")
ap.add_argument("--color-hot", default="FFF4D6")
ap.add_argument("--color-mid", default="FF8A1F")
ap.add_argument("--color-cool", default="7A1400")
ap.add_argument("--seed", type=float, default=0.0)
ap.add_argument("--no-render", action="store_true")
A = ap.parse_args(argv)


def hex_rgba(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]  # ColorRamp is scene-linear
    return (*lin, 1.0)


# ---------------------------------------------------------------- scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
sc.render.resolution_x = sc.render.resolution_y = A.res
sc.render.resolution_percentage = 100
sc.render.film_transparent = A.mode == "alpha"
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGBA" if A.mode == "alpha" else "RGB"
sc.render.image_settings.color_depth = "8"
sc.view_settings.view_transform = "Standard"   # AgX/Filmic would desaturate the authored ramp
sc.view_settings.look = "None"
sc.frame_start, sc.frame_end = 1, A.frames
sc.render.fps = 30
sc.render.filepath = str(Path(A.out).resolve() / "frame_")
sc.world = sc.world or bpy.data.worlds.new("World")
if sc.world.node_tree is None:                 # 5.x: node trees exist by default; use_nodes is deprecated
    sc.world.use_nodes = True
bg = sc.world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0, 0, 0, 1)
bg.inputs["Strength"].default_value = 0.0

cam_data = bpy.data.cameras.new("BakeCam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 2.0                      # frame spans [-1,1]; keep effect max radius <= 0.95 (no cell-edge clipping)
cam = bpy.data.objects.new("BakeCam", cam_data)
sc.collection.objects.link(cam)
cam.location = (0, 0, 5)
cam.rotation_euler = (0, 0, 0)                  # looks down -Z onto XY plane
sc.camera = cam


def key(socket, frame, value):
    socket.default_value = value
    socket.keyframe_insert("default_value", frame=frame)


def set_interp(idblock, interp):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return
    curves = getattr(ad.action, "fcurves", None)
    if curves is None:  # Blender 5.x layered actions
        curves = [fc for layer in ad.action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = interp
            kp.easing = "EASE_OUT"


# ---------------------------------------------------------------- material (shared by both effects)
def build_material(name, radial):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"   # 4.2+
    else:
        mat.blend_method = "BLEND"
    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new
    out = N("ShaderNodeOutputMaterial")
    tc = N("ShaderNodeTexCoord")
    # UV distortion: uv' = uv + (noise.rgb - 0.5) * strength
    noise = N("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 4.0
    noise.inputs["Detail"].default_value = 6.0
    noise.noise_dimensions = "4D"              # W input exists only in 4D; W animates the noise in time
    noise.inputs["W"].default_value = A.seed
    L(tc.outputs["UV"], noise.inputs["Vector"])
    centered = N("ShaderNodeVectorMath"); centered.operation = "SUBTRACT"
    centered.inputs[1].default_value = (0.5, 0.5, 0.5)
    L(noise.outputs["Color"], centered.inputs[0])
    scaled = N("ShaderNodeVectorMath"); scaled.operation = "SCALE"
    L(centered.outputs[0], scaled.inputs[0])
    distorted = N("ShaderNodeVectorMath"); distorted.operation = "ADD"
    L(tc.outputs["UV"], distorted.inputs[0]); L(scaled.outputs[0], distorted.inputs[1])
    # shape mask
    if radial:   # disc: 1 - length(uv-0.5)*2
        sub = N("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = (0.5, 0.5, 0)
        L(distorted.outputs[0], sub.inputs[0])
        ln = N("ShaderNodeVectorMath"); ln.operation = "LENGTH"; L(sub.outputs[0], ln.inputs[0])
        shape = N("ShaderNodeMapRange"); shape.inputs["From Min"].default_value = 0.5; shape.inputs["From Max"].default_value = 0.0
        L(ln.outputs["Value"], shape.inputs["Value"])
    else:        # ring band: V across width, sin(pi*v)
        sep = N("ShaderNodeSeparateXYZ"); L(distorted.outputs[0], sep.inputs[0])
        mul = N("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = math.pi
        L(sep.outputs["Y"], mul.inputs[0])
        shape = N("ShaderNodeMath"); shape.operation = "SINE"; L(mul.outputs[0], shape.inputs[0])
    # erosion: alpha = saturate((noise - threshold) / softness) * shape
    ero_noise = N("ShaderNodeTexNoise"); ero_noise.inputs["Scale"].default_value = 7.0
    L(tc.outputs["UV"], ero_noise.inputs["Vector"])
    ero = N("ShaderNodeMapRange"); ero.clamp = True
    L(ero_noise.outputs["Fac"], ero.inputs["Value"])
    ero.inputs["To Min"].default_value, ero.inputs["To Max"].default_value = 0.0, 1.0
    shape_out = shape.outputs[0]
    alpha = N("ShaderNodeMath"); alpha.operation = "MULTIPLY"; alpha.use_clamp = True
    L(shape_out, alpha.inputs[0]); L(ero.outputs["Result"], alpha.inputs[1])
    # color ramp on alpha (hot core -> cool edge)
    ramp = N("ShaderNodeValToRGB"); el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, hex_rgba(A.color_cool)
    el[1].position, el[1].color = 1.0, hex_rgba(A.color_hot)
    mid = el.new(0.55); mid.color = hex_rgba(A.color_mid)
    L(alpha.outputs[0], ramp.inputs["Fac"])
    emis = N("ShaderNodeEmission"); L(ramp.outputs["Color"], emis.inputs["Color"])
    transp = N("ShaderNodeBsdfTransparent")
    mix = N("ShaderNodeMixShader")
    L(alpha.outputs[0], mix.inputs["Fac"]); L(transp.outputs[0], mix.inputs[1]); L(emis.outputs[0], mix.inputs[2])
    L(mix.outputs[0], out.inputs["Surface"])
    # timing: fast attack (frames 1->15%), slow decay; erosion threshold sweeps up over life
    f0, fpk, f1 = 1, max(2, round(A.frames * 0.15)), A.frames
    key(scaled.inputs["Scale"], f0, 0.05); key(scaled.inputs["Scale"], f1, 0.35)
    key(emis.inputs["Strength"], f0, 1.0); key(emis.inputs["Strength"], fpk, 4.0); key(emis.inputs["Strength"], f1, 0.6)
    key(ero.inputs["From Min"], f0, 0.0); key(ero.inputs["From Min"], f1, 0.72)
    key(ero.inputs["From Max"], f0, 0.15); key(ero.inputs["From Max"], f1, 0.80)
    key(noise.inputs["W"], f0, A.seed); key(noise.inputs["W"], f1, A.seed + 1.5)
    set_interp(nt, "LINEAR")                # erosion must sweep the full life; attack comes from the 15% peak key
    return mat


# ---------------------------------------------------------------- effects
def build_burst():
    bpy.ops.mesh.primitive_plane_add(size=2.0)     # UV 0..1 across [-1,1]
    card = bpy.context.active_object
    card.data.materials.append(build_material("VFX_Burst", radial=True))
    # scale-in: 0.35 -> 0.95 with ease-out (fast attack)
    card.scale = (0.35,) * 3; card.keyframe_insert("scale", frame=1)
    card.scale = (0.95,) * 3; card.keyframe_insert("scale", frame=max(2, round(A.frames * 0.4)))
    set_interp(card, "EXPO")
    return card


def build_ring():
    """Geometry Nodes shockwave: grid -> polar warp -> annulus with UV (U=around, V=across). Radius from Scene Time."""
    ng = bpy.data.node_groups.new("GN_ShockRing", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    s_r0 = ng.interface.new_socket("Radius Start", in_out="INPUT", socket_type="NodeSocketFloat"); s_r0.default_value = 0.1
    s_r1 = ng.interface.new_socket("Radius End", in_out="INPUT", socket_type="NodeSocketFloat"); s_r1.default_value = 0.85
    s_w = ng.interface.new_socket("Width", in_out="INPUT", socket_type="NodeSocketFloat"); s_w.default_value = 0.12
    s_d = ng.interface.new_socket("Duration Frames", in_out="INPUT", socket_type="NodeSocketFloat"); s_d.default_value = float(A.frames)
    N, L = ng.nodes.new, ng.links.new
    gin, gout = N("NodeGroupInput"), N("NodeGroupOutput")
    grid = N("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = 1.0; grid.inputs["Size Y"].default_value = 1.0
    grid.inputs["Vertices X"].default_value = 97; grid.inputs["Vertices Y"].default_value = 3
    store_uv = N("GeometryNodeStoreNamedAttribute"); store_uv.data_type = "FLOAT2"; store_uv.domain = "CORNER"
    store_uv.inputs["Name"].default_value = "UVMap"
    L(grid.outputs["Mesh"], store_uv.inputs["Geometry"]); L(grid.outputs["UV Map"], store_uv.inputs["Value"])
    # t = saturate((frame-1)/duration); ease = 1-(1-t)^3
    st = N("GeometryNodeInputSceneTime")
    fm1 = N("ShaderNodeMath"); fm1.operation = "SUBTRACT"; fm1.inputs[1].default_value = 1.0; L(st.outputs["Frame"], fm1.inputs[0])
    t = N("ShaderNodeMath"); t.operation = "DIVIDE"; t.use_clamp = True; L(fm1.outputs[0], t.inputs[0]); L(gin.outputs["Duration Frames"], t.inputs[1])
    omt = N("ShaderNodeMath"); omt.operation = "SUBTRACT"; omt.inputs[0].default_value = 1.0; L(t.outputs[0], omt.inputs[1])
    cub = N("ShaderNodeMath"); cub.operation = "POWER"; cub.inputs[1].default_value = 3.0; L(omt.outputs[0], cub.inputs[0])
    ease = N("ShaderNodeMath"); ease.operation = "SUBTRACT"; ease.inputs[0].default_value = 1.0; L(cub.outputs[0], ease.inputs[1])
    radius = N("ShaderNodeMapRange"); L(ease.outputs[0], radius.inputs["Value"])
    L(gin.outputs["Radius Start"], radius.inputs["To Min"]); L(gin.outputs["Radius End"], radius.inputs["To Max"])
    # polar warp: angle=(x+0.5)*2pi ; r = radius + y*width
    pos = N("GeometryNodeInputPosition"); sep = N("ShaderNodeSeparateXYZ"); L(pos.outputs[0], sep.inputs[0])
    xa = N("ShaderNodeMath"); xa.operation = "MULTIPLY_ADD"; xa.inputs[1].default_value = 2 * math.pi; xa.inputs[2].default_value = math.pi
    L(sep.outputs["X"], xa.inputs[0])
    w_off = N("ShaderNodeMath"); w_off.operation = "MULTIPLY"; L(sep.outputs["Y"], w_off.inputs[0]); L(gin.outputs["Width"], w_off.inputs[1])
    r = N("ShaderNodeMath"); r.operation = "ADD"; L(radius.outputs["Result"], r.inputs[0]); L(w_off.outputs[0], r.inputs[1])
    cs, sn = N("ShaderNodeMath"), N("ShaderNodeMath"); cs.operation, sn.operation = "COSINE", "SINE"
    L(xa.outputs[0], cs.inputs[0]); L(xa.outputs[0], sn.inputs[0])
    px, py = N("ShaderNodeMath"), N("ShaderNodeMath"); px.operation = py.operation = "MULTIPLY"
    L(cs.outputs[0], px.inputs[0]); L(r.outputs[0], px.inputs[1]); L(sn.outputs[0], py.inputs[0]); L(r.outputs[0], py.inputs[1])
    comb = N("ShaderNodeCombineXYZ"); L(px.outputs[0], comb.inputs["X"]); L(py.outputs[0], comb.inputs["Y"])
    setp = N("GeometryNodeSetPosition"); L(store_uv.outputs["Geometry"], setp.inputs["Geometry"]); L(comb.outputs[0], setp.inputs["Position"])
    merge = N("GeometryNodeMergeByDistance"); merge.inputs["Distance"].default_value = 1e-4
    L(setp.outputs["Geometry"], merge.inputs["Geometry"])
    setm = N("GeometryNodeSetMaterial"); setm.inputs["Material"].default_value = build_material("VFX_Ring", radial=False)
    L(merge.outputs["Geometry"], setm.inputs["Geometry"]); L(setm.outputs["Geometry"], gout.inputs["Geometry"])
    mesh = bpy.data.meshes.new("RingHost")
    ob = bpy.data.objects.new("ShockRing", mesh)
    sc.collection.objects.link(ob)
    ob.modifiers.new("ShockRing", "NODES").node_group = ng
    return ob


build_burst() if A.effect == "burst" else build_ring()
Path(A.out).mkdir(parents=True, exist_ok=True)
if not A.no_render:
    bpy.ops.render.render(animation=True)
print(f"[bake] done effect={A.effect} frames={A.frames} res={A.res} mode={A.mode} -> {A.out}")
```
</bake_script>

<pipeline_to_engine>
```bash
# 1) bake
blender -b --factory-startup -P tools/vfx_bake_blender.py -- --out bake/core --effect burst --frames 16 --res 256 --mode additive
# 2a) Roblox: white sprite tinted by ParticleEmitter.Color, 4x4 @1024
python scripts/vfx_atlas_packer.py extract-alpha bake/core alpha/core --mode max --white-rgb
python scripts/vfx_atlas_packer.py stitch-flipbook alpha/core out/T_FX_Core.png --grid 4x4 --max-size 1024 --padding 2 --meta out/T_FX_Core.json
# 2b) Unity: keep baked color, 8x8 @2048 (render --frames 64 --res 256)
python scripts/vfx_atlas_packer.py extract-alpha bake/core alpha/core --mode max
python scripts/vfx_atlas_packer.py stitch-flipbook alpha/core out/T_FX_Core.png --grid 8x8 --cell 256 --max-size 2048 --padding 2
# 2c) Smoke rendered with --mode alpha: stitch directly
python scripts/vfx_atlas_packer.py stitch-flipbook bake/smoke out/T_FX_Smoke.png --grid 4x4 --max-size 1024 --padding 2
```
MESH EXPORT (rings/trails/shards):
| Target | Settings |
|---|---|
| Unity FBX | Apply Modifiers ON, Forward -Z, Up Y, Apply Scalings = FBX Units Scale, Mesh only, Smoothing = Face; UVMap present |
| Roblox FBX/OBJ | Apply Modifiers ON, scale so 1 Blender m maps to intended studs (Roblox importer: check Rig/Scale in 3D Importer); keep triangle count low (single effect mesh <= 2k tris); MeshPart.TextureID = baked RGBA |
</pipeline_to_engine>

<test_procedure>
T1 Run bake with `--no-render` first: script must print `[bake] done`; inspect scene in UI if needed.
T2 Render; confirm frame count = --frames and frame 1 non-empty, last frame near-empty (fade complete).
T3 Stitch; open atlas over gray: no cell-edge clipping (effect inside 0.95 safe area), no dark halos (packer resizes premultiplied).
T4 Energy curve: per-frame summed alpha peaks within first 30% of frames (burst effects).
T5 Engine import per destination platform file; play at manifest fps; compare timing to manifest.motion_timing.
</test_procedure>

<pitfalls>
- AgX (4.x/5.x default view transform) desaturates hot colors -> always set Standard for bakes.
- Eevee bloom/glare baked into frames double-blooms in engines with post bloom.
- Keyframing node sockets: keys live on the material node tree's action; in 5.x iterate layered channelbags (script does).
- Ring/trail UVs from Geometry Nodes must be stored on CORNER domain as FLOAT2 named "UVMap" to be recognized as UV by Texture Coordinate.
- Do not per-frame recenter in Blender; motion offsets are part of the design. Packer `--recenter` uses one shared offset.
</pitfalls>
