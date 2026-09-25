# Minecraft Mod MCP — Minefed full-control build

Copyright (c) 2025 langyo. Original project:
https://github.com/langyo/minecraft-mod-mcp

Upstream v0.3.0, commit `50e059dccb09a9e23b91833ffdbf42efd97fa6e6`, offers
MIT OR Apache-2.0 OR CC0-1.0. This derivative uses the MIT option. All three
original license texts and the original copyright are preserved and embedded
in the modified JAR. No rights to Minecraft are granted.

Minefed contributors modified the client on 2026-09-26:

- Version `0.3.0+minefed.2` restores all upstream game command dispatch,
  the bundled dashboard, call history and event stream. No read-only allowlist.
- Bind only to IPv4 loopback, including automatic port fallback. Accept native
  local clients and the same-origin local dashboard, reject foreign Host/Origin.
- Bound command request bodies to 16 KiB, run eight daemon HTTP workers,
  and shut them down on stop. Upstream control mode and game permissions remain.
- `ObservationState.java` reads exact 1.20.4 named/intermediary player/world
  members on the client thread. Missing state returns an explicit error.
- `ObservationScreenshot.java` captures the actual 1.20.4 framebuffer and closes
  native images. Both screenshot command variants use this corrected capture.
- `GameplayControl.java` uses Yarn 1.20.4+build.3 named/intermediary mappings for
  keyboard input, view angles, vanilla item use, command submission and screen
  closing. Key release is scheduled off the client thread instead of sleeping
  on it. `release_all_keys` and control-mode exit release tracked held keys.
- All other upstream commands are forwarded unchanged. Nested parameters are
  JSON-serialized to the upstream string map. Server response success is not
  inferred from merely submitting a game command or item action.

The build replaces HTTP server classes, adds the three compatibility helpers,
and updates Fabric metadata; other original entries are byte-for-byte preserved.
Gson is supplied by Minecraft, not bundled. Input hashes, source pin and build
recipe are recorded in `inventory/minecraft-mcp.lock.json`. Modified source and
this notice are embedded in the JAR.

The local API is unauthenticated and supports world-changing actions. Loopback
binding is not an operating-system user isolation boundary. There is no
multiplayer bot or server-side component.

Build with Java 17: `python scripts/release_mcp.py --output build/minecraft-mcp`.
Root `AGENTS.md` repository instructions apply to this directory.
