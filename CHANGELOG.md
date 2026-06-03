# Changelog

## 0.13.0

### Added
- `set_fusion_title_text` — set the on-screen text of an existing Fusion title
  on the timeline (writes `StyledText` on every Text+ node in its Fusion comp).
- `style_fusion_title` — style + animate a Fusion (Text+) title into an opening
  card by editing its Fusion node graph: font/size/color, optional black
  Background, Glow, and a zoom-in `Size` keyframe reveal. Idempotent (re-running
  reuses its own named nodes instead of stacking duplicates) and best-effort
  (per-step `applied` report; template-incompatible steps skip, not fatal).
- `insert_fusion_title` now takes an optional `text` argument that sets the
  title's on-screen text at insert time.
- `list_fonts` — list installed font families and their English style/weight
  names (from the OS font database) so callers pick a valid Font+Style and avoid
  Fusion's "Could not find font" render error. 149 → 152 tools.

### Changed
- Clarified `insert_title` / `insert_fusion_title` docs: the `title` argument is
  the generator **template name**, not the displayed text (basic `Text` titles
  default to "Basic Title" and have no API to change it; use a Fusion title).
- Startup connect-guide log now includes how to allow every `davinci` tool at
  once (`mcp__davinci` permission rule).
- Docs: new "MCP-original tools" section in `docs/TOOLS.md` (tools with no 1:1
  Resolve API), tool-count fixes, CONTRIBUTING guide, CI matrix, start-guide
  screenshots.

### Fixed
- `subprocess` output inside Resolve's ASCII-locale Python crashed on non-ASCII
  font names; capture bytes and decode UTF-8 explicitly (`fallbacks/10`).

## 0.12.0

### Added
- id-based addressing for multi-clip tools: `delete_clip`,
  `append_clips_to_timeline`, `create_timeline_from_clips`,
  `move_clips_to_folder`, `relink_clips` now accept `ids` (resolvable across any
  bin) and/or `names` (current folder), via a shared `_resolve_clips` helper.
  Completes id-based clip addressing (single + multi).

## 0.11.0

### Added
- `get_timeline_markers` — list all markers on the current timeline
  (`Timeline.GetMarkers`). There was add/delete but no list (149 tools).

### Changed
- Tool registry now appends any `@register`'d tool not in `_TOOL_ORDER` (stable),
  so adding a tool no longer requires editing the order list; an `assert` fails
  loudly at import if a listed name is never registered.

## 0.10.0

### Added
- id-based media-pool clip addressing (MVP): single-clip tools accept a stable
  `id` (`GetUniqueId`, resolvable across any bin) as an alternative to `name`
  (current folder), fixing duplicate-name ambiguity. `list_media_pool`,
  `get_selected_clips`, `get_pool_clip_tags`, `get_clip_properties` now expose
  `id`. Folder and multi-name/list tools are unchanged for now.

## 0.9.0

### Added
- Server-side argument validation: every `tools/call` is checked against the
  tool's JSON Schema (required fields, basic types, enums) before dispatch. A
  malformed call now returns a clear `ToolError` naming the offending argument
  instead of a generic internal error. Extra args are tolerated; deeply nested
  schema constraints are not exhaustively checked.

### Changed
- Dropped dead imports left by the tools/ split (no behavior change).

## 0.8.3

Internal refactor only — no tool/behavior change (148 tools).

### Changed
- Split the 2853-line `tools.py` monolith into a `resolve_mcp/tools/` package by
  area (status, projects, timelines, tracks, editing, color, mediapool, storage,
  render, gallery) + `_helpers` + a `register`/`TOOLS` `__init__`. Public surface
  unchanged: `from resolve_mcp.tools import TOOLS, ToolError`.
- Split `tests/live_test.py` into a `tests/live/` package mirroring the same
  areas; CLI and the 147 per-feature tests are unchanged.

## 0.8.2

Edition-aware gating + a live integration test suite.

### Added
- Runtime edition detection: `get_status` reports `studio` (bool) via
  `GetProductName`. Studio-only tools now refuse on the free edition with a
  clean "requires Studio" error **without** calling the gated API — so they no
  longer trigger the upgrade dialog that wedges UI automation. Applied to
  `detect_scene_cuts` (`_require_studio` helper for future Studio tools).
- `tests/live_test.py`: one live test per tool (selectable: `python3
  tests/live_test.py <tool>`), reversible, with Studio/heavy tools skipped and
  file/destructive tools checked via their error path. 135 pass / 12 skip.

### Notes
- A few marker/still tests are sensitive to Resolve session state and skip
  (with a reason) on their known signature; the underlying tools are verified.

## 0.8.1

Hardening from a code review of the v0.7.0/v0.8.0 tool delta (no high-severity
bugs found).

### Changed
- `relink_clips` and `move_folders` now hard-fail if any requested name is
  missing (was silent partial success), matching `append_clips_to_timeline`.
- `create_timeline_from_clips` rejects an empty `names` list.

## 0.8.0

Completes the medium-value free/Lite gaps — now **148 tools** (+15).

### Added
- `get_current_video_item` — the clip under the playhead.
- Media management: `relink_clips`, `move_folders`, `link_full_resolution_media`, `replace_clip_preserve_subclip`.
- Color groups: `get_color_group_clips`, `rename_color_group`, `get_color_group_node_graph` (pre/post-clip); PowerGrade albums: `list_powergrade_albums`, `create_powergrade_album`.
- Project config I/O: `restore_project`, `get_project_presets`, `set_project_preset`, `import_render_preset`, `export_render_preset`.

### Notes
- `add_subfolder` makes the new folder current (call `set_current_folder` to add siblings).
- `export_render_preset` only exports user presets (not factory) and writes a preset bundle.

## 0.7.0

Fills the remaining high-value free/Lite gaps — now **133 tools** (+10).

### Added
- `add_render_job` — queue a render without starting it (batch queues).
- `get_timeline_item_timing` — a clip's source extents, left/right offsets, track type/index, linked items.
- Gallery still I/O: `list_gallery_stills`, `set_gallery_still_label`, `export_gallery_stills`, `import_gallery_stills`, `delete_gallery_stills`.
- `apply_grade_from_drx` — apply a .drx PowerGrade to a clip's node graph; `get_node_tools` — list a node's operators.
- `create_timeline_from_clips` — build a timeline from media-pool clips in one call.

## 0.6.0

Comprehensive coverage of the **free (Lite) API surface** — now **123 tools**
(+46), all live-verified on DaVinci Resolve Lite.

### Added
- **Bins/folders:** `add_subfolder`, `set_current_folder`, `delete_subfolders`, `move_clips_to_folder`.
- **Mark in/out:** `set_mark_in_out`, `get_mark_in_out`, `clear_mark_in_out` (timeline or pool clip; 0-based frames).
- **Compound/Fusion clips:** `create_compound_clip`, `create_fusion_clip`; `set_timeline_name`, `set_timeline_start_timecode`.
- **Color depth:** `set_cdl`, `set_clip_enabled`, grade versions (`list`/`add`/`load`/`delete`), `copy_grade`, color groups (`list`/`add`/`delete`/`assign`/`remove`), `export_lut`.
- **Media-item:** `link_proxy`, `unlink_proxy`, `replace_clip`, `get_selected_clips`, `set_selected_clip`.
- **Render:** `save_render_preset`, `delete_render_preset`, `load_render_preset`, `get_render_mode`, `set_render_mode`, `get_render_resolutions`, `get_quick_export_presets`, `quick_export`.
- **Misc:** `import_into_timeline`, `insert_audio_at_playhead`, `grab_all_stills`, `reveal_in_storage`, `export_metadata`, `refresh_lut_list`, gallery albums (`list`/`create`/`set_current`).

### Notes
- Studio-only features (transcribe, subtitles-from-audio, magic mask, stabilize, smart reframe, Dolby Vision, voice isolation, cloud projects) are intentionally omitted — they do not run on the free edition.
- `export_lut` requires the Color page open; `set_mark_in_out` frames are 0-based.

## 0.5.0

Adds source-clip (media pool) tagging — now **77 tools**.

### Added
- `get_pool_clip_tags`, `set_pool_clip_color`, `add_pool_clip_flag`,
  `clear_pool_clip_flags`, `add_pool_clip_marker`, `delete_pool_clip_marker` —
  color label, flags and markers on MediaPoolItems (mirrors the timeline-clip
  tagging set at the source-clip level).

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
