# Changelog

## 0.4.0

Rounds out timeline editing (now **71 tools**).

### Added
- `insert_title`, `insert_fusion_title`, `insert_generator` — insert a
  title/generator at the playhead.
- `delete_timeline_item` — delete a clip from the timeline (optional ripple).

## 0.3.0

Adds import / backup symmetry (now **67 tools**).

### Added
- `import_timeline` — create a timeline from an AAF/EDL/XML/FCPXML/DRT/OTIO file
  (`MediaPool.ImportTimelineFromFile`).
- `export_project` / `import_project` — back up / restore a project as a `.drp`
  (`ProjectManager.ExportProject` / `ImportProject`).

### Notes
- For DRT import the new timeline takes the file's own name (`timelineName` is
  ignored by Resolve for DRT).

## 0.2.0

Grows the tool surface from 24 → **64 tools** and hardens the server.

### Added (by area)
- **Editing:** `add_clip_to_timeline` (source in/out, target track, record frame),
  `get_timeline_item_property` / `set_timeline_item_property` (transform, crop,
  zoom, pan, opacity, …).
- **Tracks:** `add_track`, `delete_track`, `set_track_enabled`,
  `set_track_locked`, `set_track_name`.
- **Clip tagging:** `get_clip_tags`, `set_clip_color`, `add_clip_flag`,
  `clear_clip_flags`, `add_clip_marker`, `delete_clip_marker`.
- **Media pool / storage:** `get_clip_properties`, `set_clip_property`,
  `get_clip_metadata`, `set_clip_metadata`, `rename_clip`,
  `list_storage_volumes`, `browse_storage`, `add_storage_items_to_pool`.
- **Color grading:** `get_node_graph`, `set_node_lut`, `set_node_enabled`,
  `reset_grades`, `grab_still`, `get_gallery_stills_count`,
  `clear_gallery_stills`.
- **Render:** `get_render_formats`, `set_render_format_codec`, `stop_rendering`,
  `delete_render_job`.
- **Project/timeline lifecycle:** `save_project`, `create_project`,
  `close_project`, `duplicate_timeline`, `detect_scene_cuts`.
- **Settings passthrough:** `get_setting`, `set_setting` (project/timeline).

### Changed
- Refactored the single-file server into the `resolve_mcp` package with a thin
  launcher; installer ships the package to a non-menu folder (`Scripts/MCP`) so
  modules stay out of the Resolve Scripts menu. Launchers live in
  `Scripts/Utility` (shown on every page).
- Single-line per-call logging: `[davinci-mcp] <name> <args> -> ok|error (Nms)`.
- Added an offline test suite (`tests/test_server.py`, fake Resolve).

### Fixed (pre-release hardening from code review)
- Bridge fast-fails and drains on shutdown (no hung HTTP handler threads).
- `do_POST` guards a malformed `Content-Length`.
- `append_clips_to_timeline` got the missing media-folder None guard.
- `delete_render_job` rejects an empty `jobId` (no accidental clear-all).
- `set_timecode` / `open_page` raise on failure instead of reporting success.
- `get_resolve` uses `is not None` for the scripting object.

### Known limitations
- Clips are addressed by name within the current folder (duplicate names: only
  one is reachable). Tool args are schema-described but not strictly validated.

## 0.1.0

First release. A zero-dependency, stdlib-only MCP server that runs **inside**
DaVinci Resolve (including the free **Lite** edition) as a Workspace > Scripts
menu script and exposes the Resolve Python API over a localhost HTTP endpoint,
so Claude Code (or any Streamable-HTTP MCP client) can drive Resolve.

### Highlights
- Runs on the **free edition**, which blocks external scripting — by hosting the
  server inside a menu script.
- **Zero dependencies** (pure stdlib); nothing to install into Resolve's Python.
- All Resolve API calls serialized onto the main script thread via a command
  queue (HTTP handler threads enqueue and block) for thread safety.
- **52 tools**, all exercised live against DaVinci Resolve Lite.
- Per-call logging to the Console and a logfile (`~/Movies/...log`).
- Modular `resolve_mcp` package + thin launcher; offline test suite.

### Tools by area
- **Status/navigation:** get_status, open_page, get_setting, set_setting
- **Projects/timelines:** list_projects, load_project, get_project_info,
  list_timelines, set_current_timeline, create_timeline, delete_timeline,
  get_timeline_info, get_timecode, set_timecode, add_timeline_marker,
  delete_timeline_marker
- **Tracks:** add_track, delete_track, set_track_enabled, set_track_locked,
  set_track_name, get_track_items
- **Editing:** add_clip_to_timeline, append_clips_to_timeline,
  get_timeline_item_property, set_timeline_item_property, get_clip_tags,
  set_clip_color, add_clip_flag, clear_clip_flags, add_clip_marker,
  delete_clip_marker
- **Media pool/storage:** list_media_pool, import_media, delete_clip,
  get_clip_properties, set_clip_property, get_clip_metadata, set_clip_metadata,
  rename_clip, list_storage_volumes, browse_storage, add_storage_items_to_pool
- **Render/export:** export_current_frame_as_still, export_timeline,
  get_render_presets, get_render_formats, set_render_format_codec,
  render_current_timeline, get_render_status, stop_rendering, delete_render_job

### Install
`./install.sh` — copies launchers to `Fusion/Scripts/Utility` and the
`resolve_mcp` package to `Fusion/Scripts/MCP` (hidden from the menu) on the
sandboxed Lite build; symlinks on Studio.

### Known constraints
- macOS only (paths/sandbox assume the macOS Resolve layout).
- Lite sandbox: tool file paths (exports/imports) must be under `~/Movies` or
  another granted location.
