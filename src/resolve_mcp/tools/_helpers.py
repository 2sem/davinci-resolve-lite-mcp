"""Shared helper functions and schema fragments for Resolve MCP tools."""

class ToolError(Exception):
    """Raised by tools for user-facing failures."""


def _require_studio(resolve):
    """Raise (without touching the gated API) if not running DaVinci Resolve
    Studio. Calling a Studio-only API on the free edition pops an upgrade dialog
    that wedges UI automation, so we refuse up front."""
    if "Studio" not in (resolve.GetProductName() or ""):
        raise ToolError(
            "This feature requires DaVinci Resolve Studio (paid). The free "
            "edition cannot run it."
        )


def _require_project(resolve):
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject() if pm else None
    if not project:
        raise ToolError("No project is open in DaVinci Resolve.")
    return project


def _require_timeline(resolve):
    project = _require_project(resolve)
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise ToolError("No timeline is open in the current project.")
    return timeline


def _track_item(resolve, args):
    """Resolve a TimelineItem by trackType + 1-based trackIndex + 1-based itemIndex."""
    tl = _require_timeline(resolve)
    ttype = args["trackType"]
    tidx = args["trackIndex"]
    iidx = args["itemIndex"]
    items = tl.GetItemListInTrack(ttype, tidx) or []
    if iidx < 1 or iidx > len(items):
        raise ToolError(
            f"No item #{iidx} on {ttype}{tidx} (track has {len(items)} item(s))."
        )
    return items[iidx - 1]


def _walk_clips(mp):
    """Yield every MediaPoolItem in the media pool (all folders, depth-first)."""
    root = mp.GetRootFolder()
    stack = [root] if root else []
    while stack:
        folder = stack.pop()
        for clip in folder.GetClipList() or []:
            yield clip
        stack.extend(folder.GetSubFolderList() or [])


def _pool_clip(resolve, name=None, clip_id=None):
    """Resolve a MediaPoolItem by unique id (searched across all bins) or, if no
    id is given, by name in the current media pool folder. Provide one of them."""
    project = _require_project(resolve)
    mp = project.GetMediaPool()
    if clip_id:
        for clip in _walk_clips(mp):
            if clip.GetUniqueId() == clip_id:
                return clip
        raise ToolError(f"Clip with id {clip_id!r} not found in the media pool.")
    if not name:
        raise ToolError("Provide a clip 'name' or 'id'.")
    folder = mp.GetCurrentFolder()
    if not folder:
        raise ToolError("No current media pool folder.")
    for clip in folder.GetClipList() or []:
        if clip.GetName() == name:
            return clip
    raise ToolError(f"Clip {name!r} not found in current folder.")


def _resolve_clips(resolve, names=None, ids=None):
    """Resolve a list of MediaPoolItems: names from the current folder and/or
    ids from anywhere in the pool, in the order given (names first, then ids).
    Raises if any name/id is unmatched or if neither is provided."""
    mp = _require_project(resolve).GetMediaPool()
    clips, missing = [], []
    if names:
        folder = mp.GetCurrentFolder()
        by_name = {c.GetName(): c for c in (folder.GetClipList() or [])} if folder else {}
        for n in names:
            clips.append(by_name[n]) if n in by_name else missing.append(n)
    if ids:
        by_id = {c.GetUniqueId(): c for c in _walk_clips(mp)}
        for i in ids:
            clips.append(by_id[i]) if i in by_id else missing.append(i)
    if missing:
        raise ToolError(f"Clips not found: {missing}")
    if not clips:
        raise ToolError("Provide 'names' and/or 'ids'.")
    return clips


def _find_folder(mp, name):
    """Find a media-pool Folder by name, searching the whole tree from root."""
    root = mp.GetRootFolder()
    stack = [root] if root else []
    while stack:
        folder = stack.pop()
        if folder.GetName() == name:
            return folder
        stack.extend(folder.GetSubFolderList() or [])
    raise ToolError(f"Media pool folder {name!r} not found.")


def _require_gallery(resolve):
    gallery = _require_project(resolve).GetGallery()
    if not gallery:
        raise ToolError("Gallery is unavailable.")
    return gallery


def _track_items_by_index(resolve, track_type, track_index, item_indices):
    """Return TimelineItems for 1-based item_indices on a track."""
    tl = _require_timeline(resolve)
    items = tl.GetItemListInTrack(track_type, track_index) or []
    chosen = []
    for idx in item_indices:
        if idx < 1 or idx > len(items):
            raise ToolError(
                f"No item #{idx} on {track_type}{track_index} ({len(items)} item(s))."
            )
        chosen.append(items[idx - 1])
    return tl, chosen


VALID_PAGES = ("media", "cut", "edit", "fusion", "color", "fairlight", "deliver")



_ITEM_ADDR = {
    "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"]},
    "trackIndex": {"type": "integer", "minimum": 1},
    "itemIndex": {"type": "integer", "minimum": 1, "description": "1-based position on the track"},
}


_TRACK_ADDR = {
    "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"]},
    "trackIndex": {"type": "integer", "minimum": 1},
}


def _node_graph(resolve, args):
    item = _track_item(resolve, args)
    graph = item.GetNodeGraph()
    if graph is None:
        raise ToolError("This clip has no node graph.")
    return item, graph


def _current_still_album(resolve):
    gallery = _require_gallery(resolve)
    album = gallery.GetCurrentStillAlbum()
    if not album:
        raise ToolError("No current gallery still album.")
    return album


def _stills_by_index(album, indices):
    stills = album.GetStills() or []
    chosen = []
    for i in indices:
        if i < 1 or i > len(stills):
            raise ToolError(f"No still #{i} (album has {len(stills)}).")
        chosen.append(stills[i - 1])
    return chosen


def _color_group(project, name):
    for g in project.GetColorGroupsList() or []:
        if g.GetName() == name:
            return g
    raise ToolError(f"Color group {name!r} not found.")



__all__ = [
    "ToolError",
    "VALID_PAGES",
    "_ITEM_ADDR",
    "_TRACK_ADDR",
    "_require_studio",
    "_require_project",
    "_require_timeline",
    "_require_gallery",
    "_track_item",
    "_track_items_by_index",
    "_pool_clip",
    "_resolve_clips",
    "_find_folder",
    "_node_graph",
    "_current_still_album",
    "_stills_by_index",
    "_color_group",
]
