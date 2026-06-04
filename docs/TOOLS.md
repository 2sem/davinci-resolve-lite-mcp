# Tools reference

157 tools, all exercised live against DaVinci Resolve Lite (or verified on the
same code path). Every tool call is logged to the Resolve Console and the
logfile as a single line:
`[davinci-mcp] <name> <args> -> ok|error|EXCEPTION (Nms)`.

> Addressing: timeline clips are addressed by `trackType` + `trackIndex` +
> `itemIndex` (all 1-based); media-pool clips by `name` (current folder) or by
> `id` (unique, any bin — from `list_media_pool`); folders by `name`. File-path
> arguments accept `~` and are created if missing — on the sandboxed Lite build
> they must resolve under `~/Movies` or another granted location.

## Status & navigation
| Tool | What it does |
|------|--------------|
| `get_status` | Product/version, current project, timeline, page |
| `open_page` | Switch to media/cut/edit/fusion/color/fairlight/deliver |
| `get_setting` / `set_setting` | Read/write any project or timeline setting |
| `refresh_lut_list` | Refresh Resolve's LUT list after adding LUT files |

## Projects
| Tool | What it does |
|------|--------------|
| `list_projects` / `load_project` | Browse and load projects |
| `get_project_info` | Name, framerate, resolution, timeline count |
| `save_project` / `create_project` / `close_project` / `restore_project` | Project lifecycle |
| `get_project_presets` / `set_project_preset` | Project presets |
| `export_project` / `import_project` | Back up / restore a project (.drp) |

## Timelines
| Tool | What it does |
|------|--------------|
| `list_timelines` / `set_current_timeline` | Browse and switch timelines |
| `create_timeline` / `create_timeline_from_clips` / `delete_timeline` / `duplicate_timeline` | Create (empty or from clips) / delete / duplicate |
| `get_timeline_info` | Frame range, timecode, track counts |
| `set_timeline_name` / `set_timeline_start_timecode` | Rename / set start TC |
| `get_timecode` / `set_timecode` | Read / move the playhead |
| `get_timeline_markers` / `add_timeline_marker` / `delete_timeline_marker` | List / add / delete timeline markers |
| `set_mark_in_out` / `get_mark_in_out` / `clear_mark_in_out` | In/out marks (timeline or pool clip; 0-based) |
| `detect_scene_cuts` | Detect & apply scene cuts |
| `export_timeline` / `import_timeline` | Export / import (AAF/EDL/FCPXML/DRT/OTIO) |
| `import_into_timeline` | Import AAF items into the current timeline |

## Tracks
| Tool | What it does |
|------|--------------|
| `add_track` / `delete_track` | Add / remove a video/audio/subtitle track |
| `set_track_enabled` / `set_track_locked` / `set_track_name` | Toggle / lock / rename |
| `get_track_items` | Clips on a track |
| `get_timeline_item_timing` | A clip's source extents, offsets, track location, linked items |
| `get_current_video_item` | The video clip under the playhead |

## Editing (timeline clips)
| Tool | What it does |
|------|--------------|
| `add_clip_to_timeline` | Place a clip with source in/out, target track, record frame |
| `append_clips_to_timeline` | Append whole clips |
| `delete_timeline_item` | Delete a clip (optional ripple — closes the gap) |
| `split_clip` | Blade/razor a clip into two contiguous clips at a frame (also splits linked audio/video + re-links, by default) |
| `cut_range` | Remove a frame range [begin,end) and close the gap (blade + manual ripple) |
| `insert_clip_fusion_transform` / `edit_clip_fusion_transform` / `remove_clip_fusion_transform` | Animate a clip's zoom/pan/rotate via a Fusion Transform (keyframed; the Edit-page transform can't be keyframed via the API) |
| `insert_title` / `insert_fusion_title` / `insert_generator` | Insert title/generator at playhead (`insert_fusion_title` takes optional `text`) |
| `set_fusion_title_text` | Set on-screen text of an existing Fusion title (StyledText) |
| `style_fusion_title` | Style + animate a Fusion title (font/size/color, Background + Glow nodes, zoom-in keyframes) |
| `list_fonts` | List installed font families + English styles/weights (pick a valid Font+Style for titles) |
| `create_compound_clip` / `create_fusion_clip` | Group items into a compound / Fusion clip |
| `insert_audio_at_playhead` | Insert audio on the current Fairlight track |
| `get_timeline_item_property` / `set_timeline_item_property` | Transform/crop/zoom/pan/opacity etc. |
| `set_clip_enabled` | Enable/disable (mute) a clip |
| `get_clip_tags` / `set_clip_color` | Clip color, flags, markers |
| `add_clip_flag` / `clear_clip_flags` | Clip flags |
| `add_clip_marker` / `delete_clip_marker` | Per-clip markers |

## Media pool & storage
| Tool | What it does |
|------|--------------|
| `list_media_pool` / `import_media` / `delete_clip` | Browse / import / delete pool clips |
| `add_subfolder` / `set_current_folder` / `delete_subfolders` | Bin management |
| `move_clips_to_folder` | Move clips into another bin |
| `get_clip_properties` / `set_clip_property` | Read/write clip properties (resolution, fps…) |
| `get_clip_metadata` / `set_clip_metadata` / `rename_clip` | Clip metadata and rename |
| `get_pool_clip_tags` / `set_pool_clip_color` | Source-clip color/flags/markers |
| `add_pool_clip_flag` / `clear_pool_clip_flags` | Source-clip flags |
| `add_pool_clip_marker` / `delete_pool_clip_marker` | Source-clip markers |
| `get_selected_clips` / `set_selected_clip` | Pool selection |
| `link_proxy` / `unlink_proxy` / `replace_clip` / `replace_clip_preserve_subclip` | Proxy media & replace |
| `link_full_resolution_media` / `relink_clips` | Relink full-res / relink by folder |
| `move_folders` | Move bins into another bin |
| `export_metadata` | Export clip metadata to CSV |
| `list_storage_volumes` / `browse_storage` / `add_storage_items_to_pool` | Disk browse + import |
| `reveal_in_storage` | Reveal a path in Media Storage |

## Color grading
| Tool | What it does |
|------|--------------|
| `get_node_graph` | Node count, labels, LUTs |
| `set_node_lut` / `set_node_enabled` | Apply a LUT to / enable a node |
| `set_cdl` | Apply an ASC CDL to a node |
| `reset_grades` | Reset all grades on a clip |
| `copy_grade` | Copy a clip's grade to other clips |
| `list_grade_versions` / `add_grade_version` / `load_grade_version` / `delete_grade_version` | Color versions |
| `list_color_groups` / `add_color_group` / `delete_color_group` | Color groups |
| `assign_to_color_group` / `remove_from_color_group` | Group membership |
| `get_color_group_clips` / `rename_color_group` / `get_color_group_node_graph` | Group inspection |
| `list_powergrade_albums` / `create_powergrade_album` | PowerGrade albums |
| `export_lut` | Export a LUT from a clip's grade (Color page) |
| `grab_still` / `grab_all_stills` | Grab stills to the gallery |
| `get_gallery_stills_count` / `clear_gallery_stills` | Count / clear stills |
| `list_gallery_albums` / `create_gallery_album` / `set_current_gallery_album` | Gallery albums |
| `list_gallery_stills` / `set_gallery_still_label` | List / label stills |
| `export_gallery_stills` / `import_gallery_stills` / `delete_gallery_stills` | Export / import / delete stills |
| `apply_grade_from_drx` | Apply a .drx PowerGrade to a clip |
| `get_node_tools` | List operators used in a node |

## Render & export
| Tool | What it does |
|------|--------------|
| `export_current_frame_as_still` | Export the current frame as an image |
| `get_render_presets` / `save_render_preset` / `delete_render_preset` / `load_render_preset` | Render presets |
| `import_render_preset` / `export_render_preset` | Render preset file I/O |
| `get_render_formats` / `set_render_format_codec` | Format + codec |
| `get_render_mode` / `set_render_mode` | Individual clips vs single clip |
| `get_render_resolutions` | Valid resolutions for format/codec |
| `add_render_job` / `render_current_timeline` / `get_render_status` | Queue (no start) / queue + start / progress |
| `stop_rendering` / `delete_render_job` | Stop / remove jobs |
| `get_quick_export_presets` / `quick_export` | Quick Export |

## MCP-original tools

Most tools map 1:1 onto a single Resolve scripting method (renamed to
snake_case — e.g. `insert_fusion_title` → `InsertFusionTitleIntoTimeline`,
`get_track_items` → `GetItemListInTrack`). The tools below have **no single
Resolve API equivalent**: they compose several Resolve calls into one
operation. The MCP tool name is original, not a Resolve method name.

| Tool | Composed Resolve calls |
|------|------------------------|
| `set_fusion_title_text` | `GetItemListInTrack` → `GetFusionCompByIndex` → `GetToolList("TextPlus")` → `SetInput("StyledText", …)` |
| `style_fusion_title` | `GetFusionCompByIndex` → `AddTool("Background"/"Merge"/"Glow")` → `ConnectInput` → `SetInput` + `BezierSpline` keyframes |
| `list_fonts` | no Resolve/Fusion font API exists → reads the OS font database (`system_profiler SPFontsDataType`), derives English styles from `fullname` |
| `insert_fusion_title` (with `text`) | `InsertFusionTitleIntoTimeline` → `GetFusionCompByIndex` → `GetToolList` → `SetInput` |
| `split_clip` | no blade/razor API exists → `DeleteClips` the item, then `AppendToTimeline` two clipInfo halves from the same source at exact record frames (loses the new half's grade/Fusion) |
| `cut_range` | blade at both ends, then hand-rolled ripple — `DeleteClips(False)` the block + downstream and `AppendToTimeline` the downstream shifted left (native `DeleteClips(ripple=True)` wipes the track; see fallbacks/12) |
| `insert/edit/remove_clip_fusion_transform` | Edit-page transform can't be keyframed via the API → `AddFusionComp` + `AddTool("Transform")` spliced before `MediaOut`, keyframed via `BezierSpline` on `Size`/`Angle` (`Center` for pan) |

> Basic `Text` titles cannot have their text set at all — they carry no Fusion
> composition, and Resolve exposes no text property for them. Use a Fusion
> title (`Text+`, "Background Reveal", …) when you need custom text.
