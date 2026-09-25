# Minecraft Mod MCP — Minefed observation build

Copyright (c) 2025 langyo. Original project:
https://github.com/langyo/minecraft-mod-mcp

Upstream v0.3.0, commit `50e059dccb09a9e23b91833ffdbf42efd97fa6e6`, offers
MIT OR Apache-2.0 OR CC0-1.0. This derivative uses the MIT option. The three
original license texts, including the original copyright, are retained here
and embedded in the modified JAR. No rights to Minecraft are granted.

Minefed contributors modified `McpHttpServer.java` on 2026-09-26:

- Bind only to IPv4 loopback, including the automatic port fallback.
- Expose exact `/api/status`, `/api/screenshot`, and `/api/cmd` paths only.
- Permit `ping`, `get_player_info`, `get_world_info`, and `get_screen_buttons`
  commands only. Disable input, commands, filesystem screenshot writes,
  control mode, events, history and the web control dashboard over HTTP.
- Reject browser Origin headers and non-loopback Host headers. No permissive CORS.
- Bound command request bodies, use two daemon workers, and shut them down on stop.
- Report the distinct Minefed version and observation-only status.

The build replaces the HTTP server classes and updates Fabric metadata; other
upstream entries remain unchanged. Gson is provided by Minecraft, not bundled.
The original JAR URL/hash and compile inputs are in `inventory/minecraft-mcp.lock.json`.
The modified source and this notice are also embedded in the JAR.

This local API is unauthenticated: native programs running as local users can
read it. Loopback binding and an HTTP allowlist are not an operating-system
user isolation boundary. There is no multiplayer bot or server component.

Build from the Minefed repository with Java 17:
`python scripts/release_mcp.py --output build/minecraft-mcp`

Repository instructions in the root `AGENTS.md` apply to this directory.
