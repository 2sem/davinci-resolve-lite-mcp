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
                                          │   (Workspace > Scripts > Utility)
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

`install.sh` deploys:

* the two launcher scripts into `Fusion/Scripts/Utility` (a folder Resolve scans
  for the Scripts menu; **Utility** shows on every page), and
* the `resolve_mcp` package into `Fusion/Scripts/MCP` — a folder Resolve does
  **not** scan, so the helper modules stay out of the menu.

The Lite container path is detected automatically.

> **Sandbox note (important).** DaVinci Resolve Lite is sandboxed and can only
> read its own container, `~/Movies`, and files you pick interactively. A
> symlink that points outside those locations (e.g. into a clone under
> `~/Projects`) **cannot be followed by the sandboxed app**, so the menu script
> would silently never run. For that reason `install.sh` **copies** the files
> into the container on Lite (and symlinks only on the non-sandboxed Studio
> build). **Re-run `./install.sh` after pulling updates.**
>
> Resolve enumerates only the category folders (`Utility / Comp / Tool / Edit /
> Color / Deliver`) for its Scripts menu — that is why the launchers go in
> `Utility` and the package hides in `MCP`.
>
> The same sandboxing applies to file paths you ask the tools to use:
> exports/imports should target `~/Movies` (or other granted locations),
> otherwise Resolve cannot write/read them.

## Run

1. In DaVinci Resolve: **Workspace > Scripts > Utility > davinci_mcp_server**.
2. Open **Workspace > Console** — it prints the endpoint and port:

   ```
   MCP endpoint:  http://127.0.0.1:8765/mcp
   Add to Claude Code:
     claude mcp add --transport http davinci http://127.0.0.1:8765/mcp
   ```

   > The startup guide prints to the Resolve Console (Workspace > Console).
   > Because the server runs continuously, its Console output can buffer until
   > it stops, so both scripts also mirror every line to a logfile:
   >
   > ```
   > ~/Movies/davinci-resolve-lite-mcp.log
   > ```
   >
   > Watch it live with `./logs.sh`. (Override the directory with
   > `DAVINCI_MCP_LOG_DIR`.) `~/Movies` is used because the sandboxed Lite app
   > is allowed to write there.

3. Register it with Claude Code:

   ```bash
   claude mcp add --transport http davinci http://127.0.0.1:8765/mcp
   ```

4. Ask Claude to control Resolve.

### Stopping

Any of these stops the server:

* **From the menu:** Workspace > Scripts > Utility > **stop_davinci_mcp_server**
* **From a terminal:** `./stop.sh`
* **Quit DaVinci Resolve**

The menu stop script and `stop.sh` both POST to the server's `/shutdown`
endpoint, scanning the same port range the server uses on startup.

> The port auto-increments from `8765` if that port is busy. Override the
> default with the `DAVINCI_MCP_PORT` / `DAVINCI_MCP_HOST` environment
> variables before launching Resolve.

## Tools

71 tools, all exercised live against DaVinci Resolve Lite.

**Status & navigation**
| Tool | What it does |
|------|--------------|
| `get_status` | Product/version, current project, timeline, page |
| `open_page` | Switch to media/cut/edit/fusion/color/fairlight/deliver |
| `get_setting` / `set_setting` | Read/write any project or timeline setting |

**Projects & timelines**
| Tool | What it does |
|------|--------------|
| `list_projects` / `load_project` | Browse and load projects |
| `get_project_info` | Name, framerate, resolution, timeline count |
| `list_timelines` / `set_current_timeline` | Browse and switch timelines |
| `create_timeline` / `delete_timeline` / `duplicate_timeline` | Create / delete / duplicate a timeline |
| `get_timeline_info` | Frame range, timecode, track counts |
| `get_timecode` / `set_timecode` | Read / move the playhead |
| `add_timeline_marker` / `delete_timeline_marker` | Timeline markers (by frame or color) |
| `detect_scene_cuts` | Detect & apply scene cuts on the timeline |
| `save_project` / `create_project` / `close_project` | Project lifecycle |

**Tracks**
| Tool | What it does |
|------|--------------|
| `add_track` / `delete_track` | Add / remove a video/audio/subtitle track |
| `set_track_enabled` / `set_track_locked` / `set_track_name` | Toggle / lock / rename a track |
| `get_track_items` | Clips on a track |

**Editing (timeline clips)**
| Tool | What it does |
|------|--------------|
| `add_clip_to_timeline` | Place a clip with source in/out, target track, record frame |
| `append_clips_to_timeline` | Append whole clips to the timeline |
| `delete_timeline_item` | Delete a clip from the timeline (optional ripple) |
| `insert_title` / `insert_fusion_title` / `insert_generator` | Insert a title/generator at the playhead |
| `get_timeline_item_property` / `set_timeline_item_property` | Transform/crop/zoom/pan/opacity etc. |
| `get_clip_tags` | A clip's color, flags and markers |
| `set_clip_color` / `add_clip_flag` / `clear_clip_flags` | Clip color label and flags |
| `add_clip_marker` / `delete_clip_marker` | Per-clip markers |

**Media pool & storage**
| Tool | What it does |
|------|--------------|
| `list_media_pool` / `import_media` / `delete_clip` | Browse / import / delete pool clips |
| `get_clip_properties` / `set_clip_property` | Read/write clip properties (resolution, fps…) |
| `get_clip_metadata` / `set_clip_metadata` / `rename_clip` | Clip metadata and rename |
| `list_storage_volumes` / `browse_storage` | List volumes / browse a disk folder |
| `add_storage_items_to_pool` | Import file/folder paths from disk into the pool |

**Color grading**
| Tool | What it does |
|------|--------------|
| `get_node_graph` | Inspect a clip's color node graph (count, labels, LUTs) |
| `set_node_lut` / `set_node_enabled` | Apply a LUT to / enable a node |
| `reset_grades` | Reset all grades on a clip's node graph |
| `grab_still` / `get_gallery_stills_count` / `clear_gallery_stills` | Grab / count / clear gallery stills |

**Render & export**
| Tool | What it does |
|------|--------------|
| `export_current_frame_as_still` | Export the current frame as an image |
| `export_timeline` / `import_timeline` | Export / import a timeline (AAF/EDL/FCPXML/DRT/OTIO) |
| `export_project` / `import_project` | Back up / restore a project (.drp) |
| `get_render_presets` | List render presets + current format/codec |
| `get_render_formats` / `set_render_format_codec` | Discover / set render format + codec |
| `render_current_timeline` | Queue + start a render of the current timeline |
| `get_render_status` | Render progress + job queue |
| `stop_rendering` / `delete_render_job` | Stop rendering / remove queued jobs |

Every tool call is logged to the Resolve Console and the logfile as a single
line: `[davinci-mcp] <name> <args> -> ok|error|EXCEPTION (Nms)`.

## Project layout

```
src/davinci_mcp_server.py        thin launcher (deployed to Scripts/Utility)
src/stop_davinci_mcp_server.py   stop launcher
src/resolve_mcp/                 the server package (deployed to Scripts/MCP, hidden)
    config · logio · connection · bridge · tools · server
tests/test_server.py             offline tests (fake Resolve, no app needed)
install.sh · uninstall.sh · stop.sh · logs.sh
fallbacks/                       documented gotchas + fixes
```

Run the offline tests with `python3 tests/test_server.py`.

## Known limitations

- Clips are addressed by **name within the current media-pool folder**; if two
  clips share a name, only one is reachable. (A future version may add id-based
  addressing.)
- Tool arguments are described by JSON Schema but not strictly validated
  server-side yet — a malformed call surfaces as a generic JSON-RPC error rather
  than a friendly message.

## Security note

The server binds to `127.0.0.1` only, so it is reachable from your machine
only. It exposes control of DaVinci Resolve to any local process that can reach
the port — only run it on a machine you trust.

## License

MIT — see [LICENSE](LICENSE).
