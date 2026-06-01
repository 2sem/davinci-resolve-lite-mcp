# Tools reference

77 tools, all exercised live against DaVinci Resolve Lite. Every tool call is
logged to the Resolve Console and the logfile as a single line:
`[davinci-mcp] <name> <args> -> ok|error|EXCEPTION (Nms)`.

> Addressing: timeline clips are addressed by `trackType` + `trackIndex` +
> `itemIndex` (all 1-based); media-pool clips by `name` within the current
> folder. File-path arguments accept `~` and are created if missing — on the
> sandboxed Lite build they must resolve under `~/Movies` or another granted
> location.

## Status & navigation
| Tool | What it does |
|------|--------------|
| `get_status` | Product/version, current project, timeline, page |
| `open_page` | Switch to media/cut/edit/fusion/color/fairlight/deliver |
| `get_setting` / `set_setting` | Read/write any project or timeline setting |

## Projects & timelines
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

## Tracks
| Tool | What it does |
|------|--------------|
| `add_track` / `delete_track` | Add / remove a video/audio/subtitle track |
| `set_track_enabled` / `set_track_locked` / `set_track_name` | Toggle / lock / rename a track |
| `get_track_items` | Clips on a track |

## Editing (timeline clips)
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

## Media pool & storage
| Tool | What it does |
|------|--------------|
| `list_media_pool` / `import_media` / `delete_clip` | Browse / import / delete pool clips |
| `get_clip_properties` / `set_clip_property` | Read/write clip properties (resolution, fps…) |
| `get_clip_metadata` / `set_clip_metadata` / `rename_clip` | Clip metadata and rename |
| `get_pool_clip_tags` / `set_pool_clip_color` | Source-clip color, flags, markers |
| `add_pool_clip_flag` / `clear_pool_clip_flags` | Source-clip flags |
| `add_pool_clip_marker` / `delete_pool_clip_marker` | Source-clip markers |
| `list_storage_volumes` / `browse_storage` | List volumes / browse a disk folder |
| `add_storage_items_to_pool` | Import file/folder paths from disk into the pool |

## Color grading
| Tool | What it does |
|------|--------------|
| `get_node_graph` | Inspect a clip's color node graph (count, labels, LUTs) |
| `set_node_lut` / `set_node_enabled` | Apply a LUT to / enable a node |
| `reset_grades` | Reset all grades on a clip's node graph |
| `grab_still` / `get_gallery_stills_count` / `clear_gallery_stills` | Grab / count / clear gallery stills |

## Render & export
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
