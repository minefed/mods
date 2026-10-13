# Client resource loading probe

This optional test mod targets the pinned **Minecraft 1.20.4 / Fabric Loader
0.18.4 / Java 17** client with Yuushya Modelling. It is not part of release JARs.
Build with JDK 17, using the launcher's existing Fabric Loader JAR:

```powershell
javac --release 17 -encoding UTF-8 -cp <fabric-loader-0.18.4.jar> -d build/client-resource-probe/classes tools/client-resource-probe/src/audit/LoadingProbe.java
jar --create --file build/client-resource-probe.jar -C build/client-resource-probe/classes . -C tools/client-resource-probe fabric.mod.json
```

Use a disposable copy of the client profile. Copy its mods, configuration,
resource packs and options, then add the probe JAR to that copy's `mods` folder.
Launch the copied profile with the same Java version, heap size and enabled packs
for each comparison. Do not connect to a server or copy a production world.

The probe waits for the title screen and the loading overlay to finish, records
JVM uptime, performs two resource reloads three seconds apart, and closes the
client. `probe-results.tsv` records wall-clock milliseconds and explicit success
or failure. On startup and after each reload it verifies all 128 registered
showblock state models, their facing and backup model, the item model, and an
unrelated vanilla model. It unwraps other mods' forwarding model layers before
checking the Yuushya wrapper.

With `-Daudit.togglePack=file/probe-server-pack.zip`, put that ZIP in the disposable
profile's `resourcepacks` directory and leave it disabled initially. The two reloads
then enable and disable it through the real resource pack manager on the client
thread. Missing/already-enabled packs fail the probe. This exercises local loading
of the same pack contents, including restored base resources after removal; it does
not test server download latency, login or the server-pack acknowledgement protocol.

Optional `-Daudit.dumpRegistries=true` writes the actual registered blocks/states
and items for asset coverage investigation. Optional `-Daudit.jfr=<absolute path>`
dumps an already running JFR recording before the client exits. On Windows use a
writable ASCII path for both JFR output and repository when the JDK cannot write
recordings through a non-ASCII profile path.

For a separate correctness run, `-Daudit.digestModels=default` writes sorted
`model-digest-title.tsv`, `model-digest-apply.tsv`, and `model-digest-remove.tsv`.
It hashes the vanilla baked-quad output of every registered block's default state
and every registered item's inventory model with four fixed random seeds and all
six faces plus unculled quads. The digest includes exact vertex/UV data, tint,
direction, shade, sprite identifiers, model lighting flags and particle sprite.
Use `all` instead of `default` to cover every registered block state. Compare each
phase against the same phase in an unmodified run; server-pack textures may
legitimately differ from the base phase. The checks run on the client thread after
each timing is recorded. They add CPU work and warm caches, so keep these runs
separate from timing comparisons. These hashes do not cover item override
predicates, block entity rendering, or custom Fabric renderer emission paths.

The original order-sensitive hashes remain unchanged. The same run additionally
writes `model-digest-canonical-<phase>.tsv`, sorting complete serialized quad records
**within each seed and requested-face group** before hashing. It preserves quad
multiplicity, vertex order, every integer/float/UV bit, tint, direction, shade and
sprite identifiers, as well as the model flags and particle sprite. This distinguishes
quad-list ordering differences from changed geometry or materials. Vanilla generated
items store their front/back faces in a `HashMap` keyed by direction enums, whose
iteration order can differ between JVM launches. Canonical equality alone does not
prove draw order is visually irrelevant, so retain and inspect ordered differences.

For a narrow raw comparison, add
`-Daudit.dumpModelQuads=automobility:crowbar#inventory,minecraft:iron_ingot#inventory`.
With model digests enabled, it writes `model-quad-dump-<phase>.tsv`: kind, model ID,
seed, requested face, original quad index and the complete serialized quad in hex.
At most 16 exact model IDs may be selected. This is a diagnostic output only; the
probe does not reorder or mutate the actual baked model.

Optional `-Daudit.scenaStatistics=true` records Scena absent-loader cache hits,
misses, retained entries and retained bytes immediately after each timing is
recorded. Counts are cumulative for that client process; use phase differences
to assess reuse. Older compatibility JARs record `unavailable`. This option works
without model digests and does not include its work in the recorded reload time.

After each run, summarize resource warnings separately:

```powershell
python scripts/audit_client_log.py <copied-profile>/logs/latest.log --output build/client-resource-diagnostics.json
```

`--strict` rejects remaining resource diagnostics or an absent completed startup.
Successful timing and wrapper checks do not establish every model's visual
correctness, world compatibility, or successful server authentication. Use repeated
runs and report background build activity rather than treating one timing as a
hardware-independent guarantee.
