"""Resolve MCP tool registry."""

from ._helpers import ToolError

TOOLS = {}


def register(name, description, schema):
    def decorator(fn):
        TOOLS[name] = {
            "description": description,
            "inputSchema": schema or {"type": "object", "properties": {}},
            "handler": fn,
        }
        return fn

    return decorator


# Imported for side-effect registrations.
from . import status  # noqa: E402,F401
from . import projects  # noqa: E402,F401
from . import timelines  # noqa: E402,F401
from . import tracks  # noqa: E402,F401
from . import editing  # noqa: E402,F401
from . import color  # noqa: E402,F401
from . import mediapool  # noqa: E402,F401
from . import storage  # noqa: E402,F401
from . import render  # noqa: E402,F401
from . import gallery  # noqa: E402,F401

_TOOL_ORDER = [
    'get_status',
    'open_page',
    'list_projects',
    'load_project',
    'get_project_info',
    'list_timelines',
    'set_current_timeline',
    'get_timeline_info',
    'get_track_items',
    'get_timeline_item_property',
    'get_timeline_item_timing',
    'set_timeline_item_property',
    'get_clip_tags',
    'set_clip_color',
    'add_clip_flag',
    'clear_clip_flags',
    'add_clip_marker',
    'delete_clip_marker',
    'get_node_graph',
    'set_node_lut',
    'set_node_enabled',
    'reset_grades',
    'apply_grade_from_drx',
    'get_node_tools',
    'grab_still',
    'add_track',
    'delete_track',
    'set_track_enabled',
    'set_track_locked',
    'set_track_name',
    'delete_timeline_item',
    'insert_title',
    'insert_fusion_title',
    'set_fusion_title_text',
    'style_fusion_title',
    'list_fonts',
    'insert_generator',
    'get_current_video_item',
    'get_timecode',
    'set_timecode',
    'get_timeline_markers',
    'add_timeline_marker',
    'delete_timeline_marker',
    'list_media_pool',
    'import_media',
    'list_storage_volumes',
    'browse_storage',
    'add_storage_items_to_pool',
    'delete_clip',
    'get_clip_properties',
    'set_clip_property',
    'get_clip_metadata',
    'set_clip_metadata',
    'rename_clip',
    'get_pool_clip_tags',
    'set_pool_clip_color',
    'add_pool_clip_flag',
    'clear_pool_clip_flags',
    'add_pool_clip_marker',
    'delete_pool_clip_marker',
    'append_clips_to_timeline',
    'add_clip_to_timeline',
    'split_clip',
    'cut_range',
    'insert_clip_fusion_transform',
    'edit_clip_fusion_transform',
    'remove_clip_fusion_transform',
    'create_timeline',
    'create_timeline_from_clips',
    'delete_timeline',
    'export_current_frame_as_still',
    'get_render_presets',
    'render_current_timeline',
    'add_render_job',
    'get_render_status',
    'stop_rendering',
    'delete_render_job',
    'get_render_formats',
    'set_render_format_codec',
    'export_timeline',
    'import_timeline',
    'export_project',
    'import_project',
    'restore_project',
    'get_project_presets',
    'set_project_preset',
    'import_render_preset',
    'export_render_preset',
    'get_setting',
    'set_setting',
    'save_project',
    'create_project',
    'close_project',
    'duplicate_timeline',
    'detect_scene_cuts',
    'get_gallery_stills_count',
    'clear_gallery_stills',
    'list_gallery_stills',
    'set_gallery_still_label',
    'export_gallery_stills',
    'import_gallery_stills',
    'delete_gallery_stills',
    'add_subfolder',
    'set_current_folder',
    'delete_subfolders',
    'move_clips_to_folder',
    'set_mark_in_out',
    'get_mark_in_out',
    'clear_mark_in_out',
    'create_compound_clip',
    'create_fusion_clip',
    'set_timeline_name',
    'set_timeline_start_timecode',
    'set_cdl',
    'set_clip_enabled',
    'list_grade_versions',
    'add_grade_version',
    'load_grade_version',
    'delete_grade_version',
    'copy_grade',
    'list_color_groups',
    'add_color_group',
    'delete_color_group',
    'assign_to_color_group',
    'remove_from_color_group',
    'get_color_group_clips',
    'rename_color_group',
    'get_color_group_node_graph',
    'list_powergrade_albums',
    'create_powergrade_album',
    'export_lut',
    'link_proxy',
    'unlink_proxy',
    'replace_clip',
    'replace_clip_preserve_subclip',
    'link_full_resolution_media',
    'relink_clips',
    'move_folders',
    'get_selected_clips',
    'set_selected_clip',
    'save_render_preset',
    'delete_render_preset',
    'load_render_preset',
    'get_render_mode',
    'set_render_mode',
    'get_render_resolutions',
    'get_quick_export_presets',
    'quick_export',
    'import_into_timeline',
    'insert_audio_at_playhead',
    'grab_all_stills',
    'reveal_in_storage',
    'export_metadata',
    'refresh_lut_list',
    'list_gallery_albums',
    'create_gallery_album',
    'set_current_gallery_album',
]
# Order known tools by _TOOL_ORDER; append any newly-registered tools not yet
# listed (stable) so adding a tool needs only @register — no _TOOL_ORDER edit.
_rank = {name: i for i, name in enumerate(_TOOL_ORDER)}
# Fail loudly if a name listed in _TOOL_ORDER was never registered (e.g. a
# renamed handler or a missing @register), instead of silently omitting it.
_missing = [n for n in _TOOL_ORDER if n not in TOOLS]
assert not _missing, f"tools in _TOOL_ORDER not registered: {_missing}"
TOOLS = dict(sorted(TOOLS.items(), key=lambda kv: _rank.get(kv[0], len(_rank))))

__all__ = ["TOOLS", "ToolError", "register"]
