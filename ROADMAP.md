# END.md

Comprehensive feature target for a Blender-equivalent CLI package.

Goal: if implemented, a user can perform essentially all Blender workflows from terminal commands, scripts, CI, and agents.

Status legend (audit date: 2026-02-15):
- [implemented] Directly supported by current CLI/bridge behavior.
- [partial] Some related support exists, but not full Blender-equivalent coverage.
- [missing] Not currently supported.

## 1. CLI Foundations

- [implemented] Stable root command (`harness-blender`)
- [partial] Consistent subcommand grammar (`<domain> <action>`)
- [implemented] JSON envelope output for commands
- [partial] `--help` coverage across command families
- [partial] Dry-run support (`run-plan --dry-run`, not global)
- [missing] Global dry-run support for all mutating commands
- [missing] Global shared flags (`--project`, `--output`, `--overwrite`) on all mutating commands
- [partial] Structured error categories with retry guidance in core flows
- [partial] Command aliases/shortcuts for common workflows
- [missing] Shell auto-completion scripts (bash/zsh/fish/PowerShell)

## 2. Bridge, Runtime, and Process Control

- [implemented] Bridge lifecycle (`start`, `serve`, `status`, `stop`, `verify`)
- [implemented] Python fallback execution (`bridge run-python`)
- [implemented] Health and RPC protocol foundations
- [partial] Bridge diagnostics depth
- [missing] Session attach/detach and multi-session orchestration
- [missing] Runtime logs streaming/tailing commands

## 3. Project and File Management

- [implemented] `file new|copy|inspect|validate|diff|snapshot|undo|redo`
- [partial] Snapshot/history lifecycle depth
- [missing] `file open|save|save-as`
- [missing] Recover auto-save / recover last session
- [missing] Link/append/make-local workflows
- [missing] Startup file defaults and app template controls
- [missing] Orphan data purge / cleanup tools

## 4. Scene, Collection, and View Layers

- [partial] Scene utility controls (`scene set-world-background`, `scene set-color-management`)
- [partial] Camera utility helpers (`scene set-orthographic`, reference images)
- [missing] Scene CRUD (`scene list|create|delete|rename|duplicate|set-active`)
- [missing] Collection management (`create|move|instance|exclude`)
- [missing] View layer management and render-pass toggles
- [missing] Scene markers and camera markers

## 5. Object Management

- [implemented] Object CRUD and transforms
- [implemented] Parenting/unparenting and batch parenting
- [implemented] Join/convert/boolean workflows
- [implemented] Shade smooth/flat and origin/apply-transform controls
- [implemented] Batch transforms (`object transform-many`)
- [partial] Selection and filtering operations breadth
- [missing] Full visibility/restrict flags parity (viewport/select/render)
- [missing] Collection linking/moving controls per object
- [missing] Single-user/instance-realize controls
- [missing] Object alignment/snap/distribute family

## 6. Mesh Modeling (Edit Mode)

- [implemented] Core edit operations (select verts, extrude, bevel verts, merge-by-distance)
- [implemented] Shape refinement (loop-cut, slide-loop, proportional-edit, bisect, clean)
- [implemented] Smoothing/subdivide operations
- [partial] Selection tooling (verts only, limited topological selection)
- [missing] Edge/face selection command families
- [missing] Knife/inset/bridge-edge-loops/fill variants/grid-fill/poke
- [missing] Normals toolkit (recalculate, flip, custom normals)
- [missing] Seam/crease/bevel-weight marking families
- [missing] Separate/split/rip/rip-fill and advanced dissolve options

## 7. Curve, Lattice, and Other Geometry Types

- [implemented] Lattice add/bind/set-point
- [implemented] Bezier curve add/set-handle/to-mesh
- [partial] Curve editing coverage (limited handle and point operations)
- [missing] NURBS/path/curve surface workflows
- [missing] Text object lifecycle and text-to-geometry workflows
- [missing] Metaball and surface object editing

## 8. Materials, Nodes, and Lookdev

- [implemented] Material create/list/assign/assign-many
- [implemented] PBR scalar controls (base color, metallic, roughness)
- [implemented] Node input set for existing material nodes
- [partial] Shader node graph control (input-level only)
- [missing] Node CRUD/linking/grouping/reroute families
- [missing] Material slot management and per-face assignment controls
- [missing] Texture/image node lifecycle and color-space management
- [missing] Bake workflows (AO/normal/emission/etc.)

## 9. Modifiers and Geometry Nodes

- [implemented] Modifier list/add/remove/apply/set
- [implemented] Geometry nodes attach/set-input
- [partial] Modifier type breadth and property parity
- [partial] Geometry nodes graph manipulation depth
- [missing] Geometry nodes node-graph CRUD
- [missing] GN simulation/bake cache controls
- [missing] Modifier stack reorder/copy/enable-disable commands

## 10. Camera, Lighting, and World

- [implemented] Camera add/list/set-active/set-lens/set-dof/look-at
- [implemented] Camera product rig helper
- [implemented] Light add/list/set-energy/set-color
- [implemented] Three-point light rig helper
- [implemented] World background and color-management basics
- [partial] Camera physical settings parity (sensor, clipping, shift, safe areas)
- [partial] Light parameter parity (shadow, radius, contact shadow, linking)
- [missing] HDRI/environment texture workflow commands
- [missing] World volumetrics/mist controls

## 11. Animation, F-Curves, NLA, Constraints

- [implemented] Timeline frame range/current frame controls
- [implemented] Keyframe insert/delete
- [implemented] F-curve list/set-interpolation
- [implemented] Action list/push-down and NLA track-add
- [implemented] Constraint add (basic)
- [partial] NLA strip-level manipulation
- [partial] Constraint configuration breadth
- [missing] Driver add/remove/expression/variables
- [missing] Motion path calculate/clear
- [missing] Retiming and keyframe batch transform tools

## 12. Rigging and Armatures

- [missing] Armature object creation/edit mode lifecycle
- [missing] Bone add/delete/extrude/subdivide/rename/mirror
- [missing] Pose mode transforms and pose library tooling
- [missing] Skinning helpers (auto weights, transfer weights)
- [missing] Weight paint utility commands

## 13. Sculpt, Paint, and Grease Pencil

- [missing] Sculpt mode command family
- [missing] Texture paint command family
- [missing] Vertex paint command family
- [missing] Weight paint command family (beyond indirect helpers)
- [missing] Grease Pencil object/layer/frame/stroke workflows

## 14. UV Editing

- [missing] UV unwrap variants (angle-based, conformal, smart)
- [missing] UV seam mark/clear operations
- [missing] UV island select/pack/align/rotate/scale
- [missing] Texel density query/set tooling
- [missing] UV layout import/export

## 15. Rendering

- [implemented] `render still|animation|status|cancel`
- [partial] Render engine/samples/resolution basic controls
- [partial] Animation output format/fps/frame-range controls
- [missing] Device/backend selection parity (CPU/GPU backend detail)
- [missing] Render pass/AOV/light group controls
- [missing] Deep output codec/container controls
- [missing] Render queue/batch farm-like orchestration
- [missing] Preview/viewport render capture controls

## 16. Simulation and Dynamics

- [missing] Rigid body workflows
- [missing] Cloth workflows
- [missing] Soft body workflows
- [missing] Fluid/Mantaflow workflows
- [missing] Particle and hair system workflows
- [missing] Collision and force field controls
- [missing] Bake/cache lifecycle commands across simulation types

## 17. Compositor, Sequencer, Tracking, and Masks

- [missing] Compositor node graph commands
- [missing] File output node and compositing preset controls
- [missing] Video Sequence Editor strip/effect workflows
- [missing] Motion tracking and camera solve commands
- [missing] Mask data-block editing workflows

## 18. Import/Export and Interchange

- [implemented] Import: GLTF/FBX/OBJ/USD
- [implemented] Export: GLTF/FBX/OBJ/USD
- [partial] Asset relink and pack/unpack external resources
- [missing] Alembic/DAE/STL/PLY/SVG/X3D/3DS/DXF format coverage
- [missing] Advanced axis/scale/material/animation conversion policies
- [missing] Batch conversion manifests with retries/checkpoints

## 19. Assets and Data-Block Management

- [implemented] Asset listing and relink-missing (basic)
- [partial] Resource pack/unpack support
- [missing] Asset mark/tag/catalog/preview generation
- [missing] Generic data-block list/inspect/rename/delete tools
- [missing] Library override create/resync/reset workflows

## 20. Analysis, Validation, and Diagnostics

- [implemented] Doctor diagnostics baseline
- [implemented] Silhouette diff analysis
- [partial] Project validation breadth
- [missing] Histogram, noise, blur, and geometry quality analytics
- [missing] Scene/animation diff tooling beyond current image-based check
- [missing] Performance benchmark commands

## 21. Batch, Automation, and Pipeline

- [implemented] Plan orchestration (`run-plan`, dry-run, rollback-on-fail)
- [partial] Reusable batch primitives via plans
- [missing] Multi-project batch runners with parallelism controls
- [missing] Conditional execution rules in plans
- [missing] Resume-failed batch checkpoints
- [missing] Pipeline publish/ingest metadata workflows

## 22. Security, Safety, and Reproducibility

- [partial] Local bridge default and deterministic JSON envelope expectations
- [partial] Idempotency metadata for many mutating responses
- [missing] Policy/allowlist command families for scripting and file access
- [missing] Resource limit controls for untrusted inputs
- [missing] Signed script/plugin trust workflows
- [missing] End-to-end reproducibility manifests for entire runs

## 23. Documentation and Parity Tracking

- [partial] Human command reference and LLM command spec docs
- [partial] Bridge protocol docs
- [missing] GUI-to-CLI Blender parity matrix
- [missing] Public milestone changelog tied to parity buckets
- [missing] Automated parity test harness by Blender feature area

## Suggested Command Namespace Shape

- `bridge *`
- `system *`
- `file *`
- `scene *`
- `object *`
- `mesh *`
- `curve *`
- `lattice *`
- `material *`
- `node *`
- `modifier *`
- `geometry-nodes *`
- `camera *`
- `light *`
- `timeline *`
- `keyframe *`
- `fcurve *`
- `action *`
- `nla *`
- `constraint *`
- `armature *`
- `pose *`
- `uv *`
- `sculpt *`
- `paint *`
- `grease-pencil *`
- `render *`
- `sim *`
- `compositor *`
- `vse *`
- `tracking *`
- `asset *`
- `data *`
- `import *`
- `export *`
- `analyze *`
- `batch *`
- `policy *`

This list is intentionally expansive. Treat it as the end-state target and implement in milestones.
