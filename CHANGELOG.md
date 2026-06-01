# Changelog

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
