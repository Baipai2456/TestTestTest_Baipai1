---
id: platform_roblox_studio
platform: roblox
load_when: session.platform in [roblox, blender->roblox]
custom_shaders: false
max_image_px: 1024
deliverables: [texture/upload table, instance hierarchy, per-layer property tables, VfxPlayer ModuleScript, client LocalScript, server trigger Script, test procedure]
---

# ROBLOX STUDIO — FLIPBOOK PARTICLES + BEAMS + TRAILS + LIGHTS + LUAU CHOREOGRAPHY SPEC

<hard_constraints>
| ID | Constraint | Consequence for the pipeline |
|---|---|---|
| RB01 | Uploaded images larger than 1024x1024 are downscaled to fit 1024 | Author atlases at exactly 1024 (or 512/256); `--max-size 1024` on every packer call |
| RB02 | No custom shaders / no material graphs for particles | Erosion, UV distortion, edge glow, soft particles must be BAKED into flipbook frames (Blender) or faked by Transparency/Size curves |
| RB03 | Particle/Beam/Trail textures are sampled as authored RGBA | Channel packing (R/G/B semantic masks) is NOT usable; ship straight RGBA looks |
| RB04 | Texture color is multiplied by `Color` (ColorSequence) | Author white/grayscale textures (`extract-alpha --white-rgb`) and color in-engine; or pre-colored flipbooks with `Color` = white |
| RB05 | Flipbook grids limited to `Enum.ParticleFlipbookLayout` Grid2x2, Grid4x4, Grid8x8 (plus None) | packer `--grid 2x2/4x4/8x8` only |
| RB06 | PointLight/SpotLight `Range` max 60 studs | clamp manifest.extras.light.range |
| RB07 | ColorSequence/NumberSequence max 20 keypoints; NumberSequence/ColorSequence are not tweenable | fade sequences via Heartbeat rebuild (see VfxPlayer) |
| RB08 | Visual effects should run on clients; server replication of per-frame property changes is wasteful | server fires RemoteEvent; each client plays the effect locally |
| RB09 | Asset IDs come only from the user's uploads (Asset Manager / Creator Hub) | NEVER invent `rbxassetid://` numbers; config fields + runtime warning |
</hard_constraints>

<flipbook_table>
| Grid | Frames | Cell px @1024 | Cell px @512 | Use |
|---|---|---|---|---|
| 2x2 | 4 | 512 | 256 | Level 1-3 cores, slow smoke variation |
| 4x4 | 16 | 256 | 128 | Level 4-7 default |
| 8x8 | 64 | 128 | 64 | Level 8-10 high-FPS cores, fast flames |
ParticleEmitter flipbook properties:
| Property | Value rule |
|---|---|
| FlipbookLayout | Grid2x2 / Grid4x4 / Grid8x8 matching atlas |
| FlipbookMode | OneShot = play all frames once across each particle's lifetime (impacts, bursts); Loop = cycle at FlipbookFramerate (fire, auras); PingPong (pulsing energy); Random = random frame per particle (debris/smoke variants) |
| FlipbookFramerate | NumberRange; used by Loop/PingPong; fps = manifest flipbook.fps |
| FlipbookStartRandom | true for Loop smoke/fire to desync particles; false for OneShot |
| FlipbookIncompatible | READ-ONLY diagnostic string shown in Properties. Non-empty => texture rejected for the current layout (non-square / non-power-of-two / wrong size). Must be empty before delivery |
Atlas order: row-major from top-left (matches `stitch-flipbook`).
</flipbook_table>

<blend_and_light_rules>
| Look | LightEmission | LightInfluence | Brightness | Notes |
|---|---|---|---|---|
| Fire / energy / sparks (additive-like glow) | 1 | 0 | 2-6 (L1 highest) | LightEmission=1 => additive blending; LightInfluence=0 => unlit, glows in dark scenes |
| Hot smoke / embers transition | 0.3-0.6 | 0 | 1-2 | partial additive |
| Dark smoke / dust / residual | 0 | 1 | 1 | alpha-blended, lit by environment so it sits in the scene |
| Shockwave beam/ring | 1 | 0 | 2-4 | |
Bloom: `Lighting > BloomEffect` (Threshold ~0.9-1.0). Only L1 should exceed threshold to keep the value hierarchy.
</blend_and_light_rules>

<zoffset_sorting>
ZOffset (ParticleEmitter, Beam) shifts render depth toward (+) / away (-) from the camera in studs without moving the emitter. Use to force layer order and stop Z-fighting/flicker between overlapping translucent layers.
| Layer | ZOffset | manifest.render_order |
|---|---|---|
| L4_LingeringResidual | -1.0 | 1 |
| L3_DebrisSparks | 0.0 | 2 |
| L0_Anticipation | 0.5 | 3 |
| L2_SecondaryMotion | 0.75 | 4 |
| L1_CoreBurst | 1.0 | 5 |
Rule: monotonic in render_order; spacing >= 0.25; never exceed |2| (layers visibly pop through nearby geometry).
</zoffset_sorting>

<hierarchy>
```
ReplicatedStorage
└── VFX (Folder)
    ├── VfxPlayer (ModuleScript)            # code below
    ├── PlayVfx (RemoteEvent)
    └── Templates (Folder)
        └── VFX_<Effect> (Model, PrimaryPart = Root)
            └── Root (Part: Anchored, CanCollide=false, CanQuery=false, CanTouch=false, CastShadow=false, Transparency=1, Size=4,4,4)
                ├── L0_Anticipation (ParticleEmitter parented to Root: Shape=Sphere spans Root.Size, ShapeInOut=Inward)
                ├── L1_CoreBurst (Attachment)     └── Emitter (ParticleEmitter)
                ├── L2_RingA0 (Attachment) / L2_RingA1 (Attachment)
                ├── L2_Shockwave (Beam: Attachment0=L2_RingA0, Attachment1=L2_RingA1)   # or a ParticleEmitter with Orientation=VelocityPerpendicular
                ├── L3_DebrisSparks (Attachment)  └── Emitter (ParticleEmitter)
                ├── L4_LingeringResidual (Attachment) └── Emitter (ParticleEmitter)
                └── FX_Light (PointLight, Brightness=0)
StarterPlayer/StarterPlayerScripts
└── VfxClient (LocalScript)
ServerScriptService
└── VfxServer (Script)
```
ATTRIBUTES (set on each ParticleEmitter / Beam / Trail / PointLight; read by VfxPlayer):
| Attribute | Type | On | Meaning |
|---|---|---|---|
| EmitDelay | number | all | seconds relative to impact t=0 (L0 negative) |
| EmitCount | number | ParticleEmitter | burst count for `:Emit()`; 0 = use EmitDuration |
| EmitDuration | number | ParticleEmitter, Trail | >0: set Enabled=true for this many seconds (rate emission, e.g. L0 charge) |
| FadeDuration | number | Beam, Trail | seconds to fade Transparency to 1 after EmitDelay |
| WidthEnd | number | Beam | target Width0/Width1 tweened over FadeDuration (shockwave growth) |
| PeakBrightness | number | PointLight | flash peak |
| AttackTime | number | PointLight | seconds 0 -> peak |
| DecayTime | number | PointLight | seconds peak -> 0 |
</hierarchy>

<layer_property_tables>
All emitters: `Enabled=false` (VfxPlayer drives them), `LockedToPart=false` unless the effect follows the source, `TimeScale=1`.
| Property | L0 Anticipation | L1 CoreBurst | L2 ring (ParticleEmitter variant) | L3 DebrisSparks | L4 Residual |
|---|---|---|---|---|---|
| Texture | soft dot/spark | core flipbook | ring sprite | spark streak | smoke flipbook |
| EmitDelay / EmitCount / EmitDuration | -0.25 / 0 / 0.25 | 0 / 3 / 0 | 0.02 / 1 / 0 | 0.03 / 30 / 0 | 0.1 / 6 / 0 |
| Rate | 60 | 0 | 0 | 0 | 0 |
| Lifetime | 0.2-0.25 | 0.6-0.7 | 0.45 | 0.4-0.8 | 1.0-1.4 |
| Speed | 0 | 0 | 0.01 (non-zero velocity required for VelocityPerpendicular to orient) | 25-45 | 2-5 |
| Shape / ShapeStyle / ShapeInOut | Sphere / Surface / Inward (emitter parented to Root part sized 4x4x4 for shape volume) | point (Attachment parent) | point (Attachment parent) | point (Attachment parent) | point (Attachment parent) |
| SpreadAngle | 0,0 | 0,0 | 0,0 | 180,180 | 180,180 |
| Size (NumberSequence) | 0:1.8, 1:0.3 | 0:2.5, 0.15:4.5, 1:5.5 | 0:1, 1:9 | 0:0.3, 1:0 | 0:3, 1:5.5 |
| Transparency | 0:1, 0.3:0.4, 1:1 | 0:1, 0.05:0, 0.7:0.4, 1:1 | 0:0.1, 1:1 | 0:0, 0.8:0, 1:1 | 0:0, 0.6:0.3, 1:1 |
| Color | #FF8A1F -> #FFF4D6 | #FFF4D6 -> #FF8A1F -> #7A1400 | #FFF4D6 -> #FF8A1F | #FFF4D6 -> #FF8A1F | #2B2B2B |
| LightEmission / LightInfluence / Brightness | 1 / 0 / 2 | 1 / 0 / 4 | 1 / 0 / 3 | 1 / 0 / 3 | 0 / 1 / 1 |
| Orientation | FacingCamera | FacingCamera | VelocityPerpendicular (EmissionDirection=Top => flat on ground) | VelocityParallel | FacingCamera |
| Rotation / RotSpeed | 0-360 / 0 | 0-360 / 0 | 0 / 0 | 0 / 0 | 0-360 / -20..20 |
| Acceleration / Drag | 0 / 0 | 0 / 0 | 0 / 0 | (0,-30,0) / 6 | (0,1.5,0) / 1 |
| Squash | — | — | — | 0:-1.5 (stretch along velocity; verify look) | — |
| FlipbookLayout / Mode | None | Grid4x4 / OneShot | None | None | Grid4x4 / Random or OneShot |
| ZOffset | 0.5 | 1.0 | 0.75 | 0 | -1 |
NOTE: Transparency is inverse alpha (0 = opaque). Convert manifest alpha keypoints with `transparency = 1 - alpha`.
Speed with Rate=0 + Emit(): particles still use Speed/SpreadAngle/Shape at the moment of Emit.
BEAM (L2 shockwave or slash): Texture = ring/slash strip; TextureMode=Stretch (slash) or Wrap (energy flow); TextureSpeed 1-3 (scroll = fake UV distortion); Segments 10-30; CurveSize0/1 for arcs; FaceCamera=true for billboard ribbons, false for ground rings; Width0/Width1 start values; LightEmission=1; ZOffset per table.
TRAIL (L2 projectile/weapon): Attachment0/Attachment1 on the moving part, spaced = ribbon width; Lifetime 0.15-0.35; MinLength 0.05; MaxLength 0 (unlimited) or capped; WidthScale 0:1, 1:0; Transparency 0:0, 1:1; FaceCamera=true for thin streaks; TextureMode=Stretch; LightEmission=1; Enabled toggled by script.
POINTLIGHT: Color = manifest.extras.light.color_hex, Range = min(manifest range, 60), Shadows=false (cost) unless L>=9, Brightness=0 at rest.
</layer_property_tables>

<fake_shader_techniques>
| Unity/Blender shader feature | Roblox emulation |
|---|---|
| Lifetime alpha erosion | Bake erosion into flipbook frames (Blender) + FlipbookMode=OneShot |
| UV distortion | Bake into frames; or Beam TextureSpeed scroll with Wrap mode |
| Edge glow / burn edge | Bake; or second emitter with smaller Size, higher Brightness, LightEmission=1 |
| Soft particles | Keep large sprites off surfaces (Shape offset upward); ZOffset; fade Transparency near end of life |
| Distortion/heat haze | Not available; replace with faint additive wavy flipbook |
| HDR emission | Brightness > 1 + LightEmission=1 + Lighting.Bloom |
| Flowmaps | Bake flowed result into frames |
</fake_shader_techniques>

<luau_module file="ReplicatedStorage/VFX/VfxPlayer (ModuleScript)">
```lua
--!nonstrict
-- VfxPlayer: client-side layered VFX playback (Emit bursts, timed rate emission, beam/trail fades, light flash, camera shake).
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Debris = game:GetService("Debris")
local Workspace = game:GetService("Workspace")

local VfxPlayer = {}

local SHAKE_BIND = "VfxPlayerCameraShake"
local activeShakes = {}

local function num(inst, name, default)
	local v = inst:GetAttribute(name)
	if typeof(v) == "number" then
		return v
	end
	return default
end

local function scaleSequence(seq, k)
	local kps = table.create(#seq.Keypoints)
	for i, kp in seq.Keypoints do
		kps[i] = NumberSequenceKeypoint.new(kp.Time, kp.Value * k, kp.Envelope * k)
	end
	return NumberSequence.new(kps)
end

local function validateTexture(inst)
	local tex = inst.Texture
	if tex == "" or tex == "rbxassetid://0" then
		warn(("[VfxPlayer] %s has no texture asset id set"):format(inst:GetFullName()))
	end
	if inst:IsA("ParticleEmitter") and inst.FlipbookLayout ~= Enum.ParticleFlipbookLayout.None then
		local ok, msg = pcall(function()
			return inst.FlipbookIncompatible
		end)
		if ok and typeof(msg) == "string" and msg ~= "" then
			warn(("[VfxPlayer] %s flipbook incompatible: %s"):format(inst:GetFullName(), msg))
		end
	end
end

-- Multiply authored opacity by (1 - f) over `duration`, preserving the authored Transparency curve shape.
local function fadeOut(inst, duration)
	local base = inst.Transparency.Keypoints
	local t0 = os.clock()
	local conn
	conn = RunService.Heartbeat:Connect(function()
		if not inst.Parent then
			conn:Disconnect()
			return
		end
		local f = math.clamp((os.clock() - t0) / math.max(duration, 1e-3), 0, 1)
		local kps = table.create(#base)
		for i, kp in base do
			kps[i] = NumberSequenceKeypoint.new(kp.Time, 1 - (1 - kp.Value) * (1 - f), kp.Envelope)
		end
		inst.Transparency = NumberSequence.new(kps)
		if f >= 1 then
			conn:Disconnect()
		end
	end)
end

local function shakeStep()
	local cam = Workspace.CurrentCamera
	if not cam then
		return
	end
	local now = os.clock()
	local offset = Vector3.zero
	for i = #activeShakes, 1, -1 do
		local s = activeShakes[i]
		local t = (now - s.start) / s.duration
		if t >= 1 then
			table.remove(activeShakes, i)
		else
			local decay = (1 - t) * (1 - t) -- fast attack, quadratic decay
			local ft = (now - s.start) * s.frequency
			offset += Vector3.new(
				math.noise(ft, s.seed, 0),
				math.noise(s.seed, ft, 0),
				0
			) * (s.amplitude * decay * 2)
		end
	end
	if #activeShakes == 0 then
		RunService:UnbindFromRenderStep(SHAKE_BIND)
		return
	end
	cam.CFrame = cam.CFrame * CFrame.new(offset)
end

function VfxPlayer.Shake(amplitude, frequency, duration, origin, radius)
	local cam = Workspace.CurrentCamera
	if origin and radius and cam then
		local falloff = 1 - math.clamp((cam.CFrame.Position - origin).Magnitude / radius, 0, 1)
		amplitude *= falloff
	end
	if amplitude <= 1e-3 then
		return
	end
	if #activeShakes == 0 then
		RunService:BindToRenderStep(SHAKE_BIND, Enum.RenderPriority.Camera.Value + 1, shakeStep)
	end
	table.insert(activeShakes, {
		start = os.clock(),
		amplitude = amplitude,
		frequency = frequency,
		duration = duration,
		seed = math.random() * 100,
	})
end

--[[ VfxPlayer.Play(template, cframe, opts?) -> Model
	opts.scale: number (default 1)            -- uniform size multiplier
	opts.parent: Instance (default workspace)  -- e.g. a VFX folder ignored by raycasts
	opts.shake: {amplitude, frequency, duration, radius}?  -- nil = read template attributes Shake* or skip
]]
function VfxPlayer.Play(template, cframe, opts)
	opts = opts or {}
	local k = opts.scale or 1
	local fx = template:Clone()
	fx:PivotTo(cframe)

	local items = {}
	local preroll = 0
	for _, d in fx:GetDescendants() do
		if d:IsA("ParticleEmitter") or d:IsA("Beam") or d:IsA("Trail") or d:IsA("PointLight") or d:IsA("SpotLight") then
			table.insert(items, d)
			preroll = math.max(preroll, -num(d, "EmitDelay", 0))
		end
		if d:IsA("Attachment") and k ~= 1 then
			d.Position *= k
		end
	end

	local endTime = 0
	for _, d in items do
		local delay = num(d, "EmitDelay", 0) + preroll
		if d:IsA("ParticleEmitter") then
			validateTexture(d)
			d.Enabled = false
			if k ~= 1 then
				d.Size = scaleSequence(d.Size, k)
				d.Speed = NumberRange.new(d.Speed.Min * k, d.Speed.Max * k)
				d.Acceleration *= k
			end
			local count = num(d, "EmitCount", 0)
			local duration = num(d, "EmitDuration", 0)
			task.delay(delay, function()
				if not d.Parent then
					return
				end
				if count > 0 then
					d:Emit(count)
				end
				if duration > 0 then
					d.Enabled = true
					task.delay(duration, function()
						if d.Parent then
							d.Enabled = false
						end
					end)
				end
			end)
			endTime = math.max(endTime, delay + duration + d.Lifetime.Max)
		elseif d:IsA("Beam") then
			validateTexture(d)
			local fade = num(d, "FadeDuration", 0.3)
			local widthEnd = d:GetAttribute("WidthEnd")
			if k ~= 1 then
				d.Width0 *= k
				d.Width1 *= k
			end
			d.Enabled = false
			task.delay(delay, function()
				if not d.Parent then
					return
				end
				d.Enabled = true
				if typeof(widthEnd) == "number" then
					local info = TweenInfo.new(fade, Enum.EasingStyle.Quart, Enum.EasingDirection.Out)
					TweenService:Create(d, info, { Width0 = widthEnd * k, Width1 = widthEnd * k }):Play()
				end
				fadeOut(d, fade)
			end)
			endTime = math.max(endTime, delay + fade)
		elseif d:IsA("Trail") then
			validateTexture(d)
			local duration = num(d, "EmitDuration", 0.3)
			d.Enabled = false
			task.delay(delay, function()
				if not d.Parent then
					return
				end
				d.Enabled = true
				task.delay(duration, function()
					if d.Parent then
						d.Enabled = false
					end
				end)
			end)
			endTime = math.max(endTime, delay + duration + d.Lifetime)
		else -- PointLight / SpotLight
			local peak = num(d, "PeakBrightness", 5)
			local attack = num(d, "AttackTime", 0.03)
			local decay = num(d, "DecayTime", 0.5)
			d.Range = math.min(d.Range * k, 60)
			d.Brightness = 0
			task.delay(delay, function()
				if not d.Parent then
					return
				end
				local up = TweenService:Create(d, TweenInfo.new(attack, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { Brightness = peak })
				up.Completed:Connect(function()
					if d.Parent then
						TweenService:Create(d, TweenInfo.new(decay, Enum.EasingStyle.Exponential, Enum.EasingDirection.Out), { Brightness = 0 }):Play()
					end
				end)
				up:Play()
			end)
			endTime = math.max(endTime, delay + attack + decay)
		end
	end

	local shake = opts.shake
	if shake == nil and fx:GetAttribute("ShakeAmplitude") then
		shake = {
			amplitude = num(fx, "ShakeAmplitude", 0),
			frequency = num(fx, "ShakeFrequency", 18),
			duration = num(fx, "ShakeDuration", 0.3),
			radius = num(fx, "ShakeRadius", 60),
		}
	end
	if shake and RunService:IsClient() then
		task.delay(preroll, VfxPlayer.Shake, shake.amplitude * k, shake.frequency, shake.duration, cframe.Position, shake.radius)
	end

	fx.Parent = opts.parent or Workspace
	Debris:AddItem(fx, endTime + 0.5)
	return fx
end

return VfxPlayer
```
</luau_module>

<client_script file="StarterPlayer/StarterPlayerScripts/VfxClient (LocalScript)">
```lua
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local vfxFolder = ReplicatedStorage:WaitForChild("VFX")
local VfxPlayer = require(vfxFolder:WaitForChild("VfxPlayer"))
local templates = vfxFolder:WaitForChild("Templates")
local playEvent = vfxFolder:WaitForChild("PlayVfx")

local fxParent = Workspace:FindFirstChild("VFXRuntime") or Instance.new("Folder")
fxParent.Name = "VFXRuntime"
fxParent.Parent = Workspace

playEvent.OnClientEvent:Connect(function(effectName, cframe, scale)
	if typeof(effectName) ~= "string" or typeof(cframe) ~= "CFrame" then
		return
	end
	local template = templates:FindFirstChild(effectName)
	if not template then
		warn("[VfxClient] unknown effect " .. effectName)
		return
	end
	VfxPlayer.Play(template, cframe, { scale = typeof(scale) == "number" and scale or 1, parent = fxParent })
end)
```
</client_script>

<server_script file="ServerScriptService/VfxServer (Script)">
```lua
-- Server-authoritative trigger. Gameplay code calls _G.PlayVfx or requires a module wrapping fire().
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local vfxFolder = ReplicatedStorage:WaitForChild("VFX")
local templates = vfxFolder:WaitForChild("Templates")
local playEvent = vfxFolder:WaitForChild("PlayVfx")

local function fire(effectName: string, cframe: CFrame, scale: number?)
	if not templates:FindFirstChild(effectName) then
		warn("[VfxServer] unknown effect " .. effectName)
		return
	end
	playEvent:FireAllClients(effectName, cframe, scale or 1)
end

_G.PlayVfx = fire -- shortcut: global accessor; replace with a ModuleScript API when the codebase has one
```
SECURITY: never connect `OnServerEvent` that lets clients request arbitrary effects without server validation (rate limit + whitelist + position sanity check).
</server_script>

<build_steps>
1. Bake/pack textures (platforms/blender_vfx.md + `--max-size 1024`). Upload via Asset Manager / Creator Hub; record returned IDs in the manifest; set Texture = `rbxassetid://<id>`.
2. Build hierarchy per <hierarchy>; set properties per <layer_property_tables>; set attributes per layer from manifest.layers[].start_s/emission.
3. Insert VfxPlayer, VfxClient, VfxServer; create RemoteEvent `PlayVfx`.
4. Set template attributes ShakeAmplitude/ShakeFrequency/ShakeDuration/ShakeRadius from manifest.extras.camera_shake (amplitude in studs).
5. Ensure `Lighting` has a `BloomEffect` if any Brightness > 1 should glow.
</build_steps>

<test_procedure>
T1 Properties panel: every flipbook emitter FlipbookIncompatible = "" (empty).
T2 Play Solo, command bar (server): `_G.PlayVfx("VFX_<Effect>", CFrame.new(0, 5, 0))`; confirm all layers appear in order.
T3 Render stats (Shift+F2) / MicroProfiler (Ctrl+F6): frame time delta at peak <= tier budget.
T4 Graphics quality slider 1 and 10 (Escape menu): effect remains readable at low quality (engine may reduce particle emission at low quality — design L1 to read with half the particles).
T5 Dark and bright skybox: LightInfluence=0 layers glow in both; smoke (LightInfluence=1) does not glow at night.
T6 Spam test: 20 plays in 2 s; no leaked instances in Workspace.VFXRuntime after 5 s (Debris cleanup).
</test_procedure>

<pitfalls>
- Emitting before parenting: VfxPlayer parents after scheduling; all Emit calls run via task.delay (next resumption), so the clone is parented first.
- Emitter on a moving part with LockedToPart=false leaves particles in world space (correct for impacts); set true for auras.
- Large additive sprites near camera = massive overdraw on mobile; cap L1 Size and particle count per tier.
- Beam textures repeat along length in Wrap mode; set TextureLength to the strip's world length to avoid stretching.
- Trail with Attachment0 and Attachment1 at the same position renders nothing (zero width).
- `Squash` sign/look varies by orientation; verify visually, otherwise use VelocityParallel + elongated texture.
</pitfalls>
