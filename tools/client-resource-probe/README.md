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

After each run, summarize resource warnings separately:

```powershell
python scripts/audit_client_log.py <copied-profile>/logs/latest.log --output build/client-resource-diagnostics.json
```

`--strict` rejects remaining resource diagnostics or an absent completed startup.
Successful timing and wrapper checks do not establish every model's visual
correctness, world compatibility, or successful server authentication. Use repeated
runs and report background build activity rather than treating one timing as a
hardware-independent guarantee.
