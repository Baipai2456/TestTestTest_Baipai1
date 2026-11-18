# Game VFX Architect Skill

A universal AI agent skill for producing real-time game VFX for **Unity (URP)**, **Roblox Studio**, and **Blender** (including Blender → Unity/Roblox bakes).

Load it into an AI coding agent (Claude Code, Cursor, Windsurf, Codex, or a multi-agent API workflow). The agent then follows a fixed pipeline: ask for the target and budget, break the effect into layers, get your approval, generate and pack 2D textures, and build the engine-side shaders, particle setups and scripts.

The skill files are written for LLMs to parse (YAML frontmatter, XML-tagged blocks, lookup tables). The agent replies to you in the language you write in, such as English or Thai.

## What it does

- **Splits every effect into layers:** `L0` anticipation, `L1` core burst, `L2` trails/shockwaves, `L3` debris/sparks, `L4` lingering smoke/residue. It never builds one monolithic effect.
- **Uses a 2D → 3D hybrid pipeline:** grayscale masks, noise and flipbooks → Python packing → driven in-engine by shaders, particle curves and scripts.
- **Asks for a 1–10 scale** for quality, time and token budget. These decide layer count, flipbook size, texture packing, and how many sub-agents run.
- **Stops for your approval** before it generates assets or writes engine code. You can skip this by saying "skip approval" or "ไม่ต้อง Approve" in your first message.
- **Audits performance** (draw calls, particle count, overdraw, texture memory) against budgets for the chosen level.

## Repository layout

```text
SKILL.md                              Router: state machine, 1-10 scale, approval gate, sub-agent dispatch
agents/
  vfx_architect_schema.md             Blueprint + layer manifest schemas, validation rules, example manifest
  asset_subagent_prompts.md           Image prompt templates, flipbook prompts, procedural texture fallback
platforms/
  unity_urp.md                        Shader Graph graph, custom vertex streams, Shuriken / VFX Graph, C# sequencer
  roblox_studio.md                    Flipbook ParticleEmitters, Beams, Trails, lights, Luau playback scripts
  blender_vfx.md                      Shader/Geometry Nodes, compositor, headless orthographic flipbook bake script
scripts/
  vfx_atlas_packer.py                 CLI: extract-alpha, stitch-flipbook, pack-channels
references/
  scale_rubric_and_budgets.md         Full 1-10 matrix, per-platform budgets, shader math, audit checklist
```

The agent loads only the platform file it needs, so a Roblox request never pulls in the Unity spec.

## Installation

Clone the repo, then point your agent at `SKILL.md`.

**Claude Code** (personal skill, available in every project):

```bash
git clone https://github.com/Baipai2456/VFX_Skill_MD_BP.git ~/.claude/skills/game-vfx-architect
```

For a single project, clone it into `<project>/.claude/skills/game-vfx-architect` instead.

**Codex:** clone into your Codex skills folder (for example `~/.codex/skills/game-vfx-architect`).

**Cursor / Windsurf / other agents:** clone the repo into your project and add a rule or instruction such as:

> For any game VFX task, read and follow `game-vfx-architect/SKILL.md`, loading only the files it references.

**API / multi-agent workflows:** use `SKILL.md` as the orchestrator's system prompt, and give the sub-agents the files listed in its routing table.

## Requirements

| Component | Needed for | Version |
|---|---|---|
| Python | `scripts/vfx_atlas_packer.py` | 3.9+ |
| Pillow, NumPy | packer | Pillow ≥ 9.1 |
| Blender | flipbook bakes, mesh trails/rings (optional) | 4.2 LTS – 5.x |
| Unity | URP target | 2022.3 LTS or Unity 6 |
| Roblox Studio | Roblox target | current |

```bash
pip install pillow numpy
```

## Using the packer directly

```bash
# Black-background render -> clean RGBA (straight alpha)
python scripts/vfx_atlas_packer.py extract-alpha frames/ alpha/ --mode max

# Frames -> 4x4 flipbook, capped at 1024 px for Roblox
python scripts/vfx_atlas_packer.py stitch-flipbook alpha/ out/T_FX_Core.png --grid 4x4 --max-size 1024 --padding 2

# Pack masks: R = shape, G = erosion, B = distortion (Unity / Blender)
python scripts/vfx_atlas_packer.py pack-channels out/T_FX_Mask.png --r shape.png --g erosion.png --b distortion.png
```

Run `python scripts/vfx_atlas_packer.py <command> --help` for all options.

Headless Blender bake (the script is inside `platforms/blender_vfx.md`):

```bash
blender -b --factory-startup -P vfx_bake_blender.py -- --out bake/core --effect burst --frames 16 --res 256
```

## Quality scale at a glance

| Level | Result |
|---|---|
| 1 | 1–2 layers, static texture or 2x2 flipbook (256 px), basic additive material |
| 5 | 3–4 layers, 4x4 flipbook + channel-packed noise, UV distortion + lifetime erosion shader |
| 10 | 5+ synchronized layers, 8x8 flipbooks, baked meshes/flowmaps, RGBA-packed masks, camera shake + light sync |

The final level is the lowest of your quality target and each budget + 2. For example, quality 10 with time budget 5 resolves to level 7.

## Platform notes

- **Roblox** has no custom shaders. Erosion, distortion and edge glow are baked into flipbook frames, and channel-packed textures are not used. Images are capped at 1024×1024.
- **Unity** relies on Custom Vertex Streams (`Custom1.xy` → `TEXCOORD0.zw`) so each particle dissolves over its own lifetime without extra materials.
- **Blender** bakes use the Standard view transform. AgX/Filmic desaturates the authored colour ramps.

## Verification status

| Part | Status |
|---|---|
| `vfx_atlas_packer.py` | Tested (alpha extraction, flipbook stitching, size cap, channel packing, error handling) |
| Blender bake script | Ran headless in Blender 5.2; burst and ring bakes stitched into 4x4 atlases |
| `VfxSequencer.cs` | Compiles against Unity 6000.3 engine assemblies |
| Luau scripts | Not yet run in Roblox Studio |
| Shader Graph / particle specs | Written specs; not yet built in a Unity project |
| Performance budgets | Production guidelines, not engine limits |

Issues and pull requests that verify the untested parts are welcome.

## License

[MIT](LICENSE) © 2026 Bp.2456
