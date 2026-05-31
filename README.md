# davinci-resolve-lite-mcp

An [MCP](https://modelcontextprotocol.io) server that lets an AI client such as
**Claude Code** control **DaVinci Resolve** — including the **free (Lite)
edition**, which the existing
[davinci-resolve-mcp](https://github.com/samuelgursky/davinci-resolve-mcp)
project cannot drive.

The free edition blocks *external* scripting, but it still runs Python scripts
launched from its own **Workspace > Scripts** menu. This project rides that path:
the MCP server runs **inside** Resolve as a menu script, and exposes Resolve's
Python API over a small local HTTP endpoint that Claude connects to.

```
Claude Code ──HTTP JSON-RPC (MCP)──▶  127.0.0.1:8765/mcp
                                          │   server runs INSIDE Resolve
                                          │   (Workspace > Scripts > Edit)
                                          ▼
                              command queue → main script thread
                                          ▼
                              global `resolve` object → Resolve API
```

## Why this works on the free edition

* Free Resolve permits scripts run from its **Scripts menu** (only *external*
  network scripting is restricted).
* A menu script gets the `resolve` object for free and may run a long-lived
  loop — long enough to host a server.
* The sandboxed Lite app ships the `com.apple.security.network.server`
  entitlement, so it can open a localhost listening socket.
* **Zero dependencies** — pure Python standard library. Nothing to `pip install`
  into Resolve's interpreter.

## Requirements

* macOS with DaVinci Resolve (Lite/free or Studio).
* Claude Code (or any MCP client that speaks the Streamable HTTP transport).

## Install

```bash
git clone <this-repo>
cd davinci-resolve-lite-mcp
./install.sh
```

`install.sh` symlinks `src/davinci_mcp_server.py` into Resolve's
`Fusion/Scripts/Edit` folder (the Lite container path is detected
automatically).

## Run

1. In DaVinci Resolve: **Workspace > Scripts > Edit > davinci_mcp_server**.
2. Open **Workspace > Console** — it prints the endpoint and port:

   ```
   MCP endpoint:  http://127.0.0.1:8765/mcp
   Add to Claude Code:
     claude mcp add --transport http davinci http://127.0.0.1:8765/mcp
   ```

3. Register it with Claude Code:

   ```bash
   claude mcp add --transport http davinci http://127.0.0.1:8765/mcp
   ```

4. Ask Claude to control Resolve.

### Stopping

Any of these stops the server:

* **From the menu:** Workspace > Scripts > Edit > **stop_davinci_mcp_server**
* **From a terminal:** `./stop.sh`
* **Quit DaVinci Resolve**

The menu stop script and `stop.sh` both POST to the server's `/shutdown`
endpoint, scanning the same port range the server uses on startup.

> The port auto-increments from `8765` if that port is busy. Override the
> default with the `DAVINCI_MCP_PORT` / `DAVINCI_MCP_HOST` environment
> variables before launching Resolve.

## Tools

| Tool | What it does |
|------|--------------|
| `get_status` | Product/version, current project, timeline, page |
| `open_page` | Switch to media/cut/edit/fusion/color/fairlight/deliver |
| `list_projects` / `load_project` | Browse and load projects |
| `get_project_info` | Name, framerate, resolution, timeline count |
| `list_timelines` / `set_current_timeline` | Browse and switch timelines |
| `create_timeline` | Create a new empty timeline |
| `get_timeline_info` | Frame range, timecode, track counts |
| `get_track_items` | Clips on a video/audio/subtitle track |
| `get_timecode` / `set_timecode` | Read / move the playhead |
| `add_timeline_marker` | Add a marker at a frame |
| `list_media_pool` / `import_media` | Browse and import media |
| `append_clips_to_timeline` | Append media-pool clips to the timeline |
| `export_current_frame_as_still` | Export the current frame as an image |
| `export_timeline` | Export timeline (AAF/EDL/FCPXML/DRT/OTIO) |
| `get_render_presets` | List render presets + current format/codec |
| `render_current_timeline` | Queue + start a render of the current timeline |
| `get_render_status` | Render progress + job queue |

## Security note

The server binds to `127.0.0.1` only, so it is reachable from your machine
only. It exposes control of DaVinci Resolve to any local process that can reach
the port — only run it on a machine you trust.

## License

MIT — see [LICENSE](LICENSE).
