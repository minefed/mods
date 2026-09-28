# Creative inventory first-frame probe

Test-only MIT code for Minecraft **1.20.4 / Fabric Loader 0.18.4 / Java 17**.
Never include this mod in the release pack. Use a new, disposable offline game
directory containing copies of the selected mods, configuration, resource packs
and options. Do not use a production world or connect to a server.

Compile the two Java sources with JDK 17 and `-proc:none`. The classpath must
contain the launcher's **intermediary-named Minecraft 1.20.4 JAR**, Fabric Loader
0.18.4, and the launcher's existing library classpath (including JOML). These are
local compile inputs, not files distributed by this repository. For example:

```powershell
javac --release 17 -proc:none -encoding UTF-8 -cp "$intermediaryJar;$launcherClasspath" -d build/creative-probe/classes tools/creative-inventory-probe/src/audit/CreativeProbe.java tools/creative-inventory-probe/src/audit/InventorySweep.java
jar --create --file build/creative-probe.jar -C build/creative-probe/classes . -C tools/creative-inventory-probe fabric.mod.json
```

Add that JAR only to the disposable profile. Set `guiScale:1`,
`fullscreen:false`, render distance 2 and simulation distance 5 in its options;
launch at 1220×680 or larger with the normal complete mod set and an 8 GB heap.
The probe creates a new creative world from the title screen. For repeat tests,
copy **only the earlier probe's disposable world** into a fresh audit directory
and use `-Daudit.reuseWorld=true --quickPlaySingleplayer <world-folder-name>`.
Do not copy PFM's generated runtime texture cache: the first pass must start cold.

The probe enumerates the real search-tab stacks after joining the world, without
calling `getModel` or `getQuads` first. A custom screen sends every stack through
Minecraft's actual GUI item renderer, 48 per page, and captures the first and
third draw. Then it reloads resources and repeats the sweep before closing the
client. This exercises the first-draw failure that a warmed model scan misses.
It does not simulate keyboard typing in the search field or every placed block.

Outputs in the disposable game directory:

- `creative-probe.tsv`: counts and explicit cold/reload completion or failure.
- `cold-` / `reload-sweep-progress.tsv`: contiguous coverage of every stack.
- `cold-` / `reload-render-candidates.tsv`: magenta pixels by page, frame and ID.
- `cold-` / `reload-page-*-frame-*.png`: candidate pages and herringbone evidence.
- Registry and creative ID lists; no item NBT, account data or coordinates.

Magenta pixels are **candidates**, not automatic texture errors. Inspect the
saved images: the rotation tool, unobtainium and magenta bit bag really contain
purple artwork. First-frame-only checkerboards identify the original PFM bug.
Do not globally exempt these item IDs from future review.

```powershell
python scripts/audit_creative_inventory.py <disposable-profile> --output build/creative-summary.json
python scripts/audit_client_log.py <disposable-profile>/logs/latest.log --require-world --output build/world-data-summary.json
```

The inventory summary rejects incomplete page coverage, missing resource-reload
passes, render exceptions and malformed evidence. A complete sweep still needs
visual review of its saved candidates. `-Daudit.skipReload=true` is available
only for diagnostic runs; it will not satisfy the default summary check.
