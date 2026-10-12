# BlueMap baked-model exporter

This **offline client tool** captures the final Fabric renderer quads from
Minecraft 1.20.4 / Fabric Loader 0.18.4 / Java 17. It is not a production mod and
must not be included in either client or server release JAR lists.

Use a new disposable game directory with copies of the selected mods,
configuration, enabled resource packs and options. Do not copy accounts or
production worlds, and do not connect to a server. The tool runs at the title
screen after resources finish loading, exports the selected models, and closes
the client. It rejects a loaded world.

Compile using JDK 17 and the launcher's intermediary Minecraft 1.20.4 JAR,
library classpath, Fabric Loader, the renderer API nested JAR from Fabric API,
and the selected Indium 1.0.31 / Sodium JARs. The optional Indium context adapter
needs these compile-only classes; no third-party class files are bundled:

```powershell
python tools/bluemap-model-exporter/build.py --jdk <jdk17-directory> --classpath-file <launcher-classpath.txt> --fabric-api <fabric-api.jar> --indium <indium.jar> --sodium <sodium.jar> --output build/bluemap-model-exporter.jar
```

The classpath file contains the intermediary client JAR and launcher libraries,
separated by the platform path separator (`;` on Windows). The helper extracts
the renderer API to a temporary compile directory, compiles every exporter source,
and includes only exporter classes, its mod manifest and MIT source license.

Add that JAR to the **disposable** profile and launch with:

```text
-Dminefed.bluemap.disposable=true
-Dminefed.bluemap.output=<fresh absolute directory under ignored build/>
-Dminefed.bluemap.namespaces=pfm,diagonalfences,diagonalwalls,diagonalwindows
```

Quote each complete `'-Dname=value'` argument when passing these through
PowerShell to a launcher script; otherwise PowerShell can split dotted names.

`-Dminefed.bluemap.blocks=minecraft:stone,pfm:oak_herringbone_planks` replaces the
namespace selection with a small explicit smoke-test selection. The output must
not already exist. The maximum is 65,536 states per block; a smaller
`-Dminefed.bluemap.maxStates=...` is useful for diagnostic runs.

The tool calls `FabricBakedModel.emitBlockQuads`, including its texture/geometry
transform stack. A `getQuads`-only implementation would silently export empty PFM
models. It writes exact four-vertex positions and UVs into the Minefed BlueMap
`bluemap_quads` extension, using 0–16 coordinates and already baked orientation.
Faces retain their cull direction, light direction, tint index, uniform vertex
RGB and diffuse-shading flag. Final sprite pixels come from the loaded client's
CPU atlas contents, so runtime-generated PFM images are included. Exported
sprites use a separate namespace to avoid changing other blocks' textures.
Square-frame vertical animations retain their full pixels, frame ordering,
durations and interpolation from the client's final `SpriteContents` metadata.
The model's ambient occlusion flag is preserved; a conflicting per-face override
is reported as unsupported rather than silently changing its lighting.
Indium optimizes its vanilla adapter with a concrete render-context cast. The
exporter's Indium subclass delegates both emitter paths and transforms to the
capture context, and rejects accidental world-lighting/buffering calls. This
preserves the selected Sodium/Indium client rather than changing its mod list.
A six-face stone capture must pass before processing the selected blocks.

Diagonal models retain their actual runtime multipart predicates. The exporter
evaluates those predicates over every registered state, compresses their exact
truth tables into vanilla multipart conditions, and captures each immutable
segment once. It verifies the full model and component union at representative
states, including every component's first/last match and a state with no active
parts when present. Normal empty wall states remain empty. This avoids creating
a separate geometry file for every combination of connected directions.
If the multipart graph is wrapped by another model, the component union is
checked against that wrapper for every registered state. The report includes
both model classes and the number of geometry checks.

For regular variant exports, `culling` and `occluding` are enabled only when
every registered state passes Minecraft's `isOpaqueFullCube` check and neither
its geometry nor that check queries neighboring blocks. Partial furniture keeps
BlueMap's conservative non-occluding default.

`export-report.json` records every selected block, state count, failures and
whether a complete blockstate replacement was written. A block replacement is
written only when **every state** passes, preventing partial variants from
overriding valid original states. `complete` means traversal finished, not that
every block is supported: inspect each `exported` value and `failures` array.

Validate every emitted blockstate, quad and texture reference before installation:

```text
python tools/bluemap-model-exporter/verify.py <export-directory>
python tools/bluemap-model-exporter/verify.py <export-directory> --require-all
```

The second form also rejects a report with any unsupported selected block. This
validator checks structural coverage and references; the actual client capture
and a BlueMap render still need separate runtime verification.

The standalone regression checks do not launch Minecraft:

```powershell
python -m unittest discover -s scripts -p test_bluemap_model_export.py
python -m unittest discover -s tools/bluemap-model-exporter/test -p test_verify.py
javac --release 17 -d build/bluemap-exporter/test tools/bluemap-model-exporter/src/team/minefed/bluemap/MultipartConditions.java tools/bluemap-model-exporter/test/team/minefed/bluemap/MultipartConditionsTest.java
java -cp build/bluemap-exporter/test team.minefed.bluemap.MultipartConditionsTest
```

By default, world-dependent models are rejected. PFM tables inspect neighboring
blocks even when the saved block state is identical; a state-only resource pack
cannot reproduce every connected placement. Explicitly selecting
`-Dminefed.bluemap.contextual=isolated` exports their normal standalone shape with
surrounding air. These states carry `minefed_export_context` metadata and the
report counts them as `isolatedContextStates`. This is a visible-model fallback,
**not verification of connected shapes**. Future neighborhood-aware rendering
must retain this distinction.

Other unsupported features are reported rather than flattened: differing
per-vertex colors or opacity, non-vertical/non-square animations, emissive materials, missing or
empty/builtin models, and random-dependent geometry detected by two seed probes.
The two probes detect common weighted models; they are not a proof for every
possible seed. Block-entity and entity renderers are outside this tool's scope.

Generated output stays local and ignored. The tool source is MIT, but its output
contains derived third-party geometry and textures under the original licenses.
PFM 1.5.0 code and visual assets are separately LGPL-3.0-only and PolyForm
Shield 1.0.0. Other models may reference Minecraft or assets with additional
restrictions. The exporter does not grant redistribution rights or label the
generated pack as MIT. Public release requires a separate asset license review;
do not copy generated JSON/PNG files into Git merely because this tool generated
them. Preserve upstream license notices when distributing any approved output.
