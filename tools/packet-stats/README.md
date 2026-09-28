# Packet statistics probe

Test-only MIT code for Minecraft **1.20.4 / Fabric Loader 0.18.4 / Java 17** dedicated servers.
Never include this mod in the release pack and never install it on the production server.
Use a disposable copy of the server directory and world.

The probe adds six observers to each connection's Netty pipeline. They only
count messages and pass every message on unchanged, so gameplay and network
bytes stay the same.

| Observer | Position | What it counts |
| --- | --- | --- |
| `minefed_stats_type` / `_in` | tail side of `encoder` / after `decoder` | packet type (after unbundling) and custom payload channel |
| `minefed_stats_plain` / `_in` | between `compress`/`decompress` and the codec | uncompressed packet bytes per type |
| `minefed_stats_wire` / `_in` | pipeline head | framed socket bytes per player (compressed when compression is on) |

Login and configuration traffic count under player `login`. Play traffic counts
under the player name. Behind Velocity, the socket figures cover the
backend–proxy link, not the proxy–player link.

**Known limitation:** when compression starts, the first compressed packet in
each direction may be counted with its compressed size. After that, the plain
observer moves back between the compressor and the codec.

## Building

Compile with JDK 17 or newer, `--release 17` and `-proc:none`. The classpath
must contain the following local compile inputs; this repository does not
distribute them:

- the **intermediary-named** Minecraft 1.20.4 server JAR, for example Loom's
  `minecraft-*-intermediary` output;
- Fabric Loader 0.18.4;
- the Fabric API modules for networking, lifecycle events and commands;
- Netty, Brigadier and authlib from the server's library directory.

```sh
javac --release 17 -proc:none -encoding UTF-8 -cp "$CLASSPATH" -d build/packet-stats/classes tools/packet-stats/src/audit/PacketStats.java
jar --create --file build/packet-stats.jar -C build/packet-stats/classes . -C tools/packet-stats fabric.mod.json
```

## Measuring

1. Copy the server, its world and its `mods/` into a disposable directory. Add
   `build/packet-stats.jar`.
2. Optional: to print Yarn class names instead of `class_XXXX`, start the
   server with
   `-Dpacketstats.mappings=/path/to/yarn-1.20.4+build.3/mappings/mappings.tiny`.
3. Optional: the automatic dump interval defaults to 60 seconds. Change it with
   `-Dpacketstats.dumpSeconds=<seconds>`.
4. Put every client in the same position, view distance and input sequence as
   in [the optimization plan](../../docs/OPTIMIZATION_PLAN_2026-09-28.md).
   Then run `/packetstats reset`, wait the fixed interval, and run
   `/packetstats dump`.
5. The server writes `packet-stats/<UTC time>-<reason>.tsv`. Repeat the run with
   the original and the optimized mods. Compare the two dumps with:

```sh
python scripts/compare_packet_stats.py before.tsv after.tsv
```

For server tick cost, measure MSPT separately with spark or `/carpet profile`.
Client frame times still come from F3+L and JFR.
