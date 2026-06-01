"""Storage Resolve MCP tools."""

import os

from . import register


@register(
    "list_storage_volumes",
    "List mounted volumes/paths shown in Resolve's Media Storage.",
    None,
)
def list_storage_volumes(resolve, args):
    ms = resolve.GetMediaStorage()
    return {"volumes": ms.GetMountedVolumeList() or []}


@register(
    "browse_storage",
    "List subfolders and media files at an absolute folder path in Media "
    "Storage (browse disk before importing).",
    {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
)
def browse_storage(resolve, args):
    ms = resolve.GetMediaStorage()
    path = os.path.expanduser(args["path"])
    return {
        "path": path,
        "subfolders": ms.GetSubFolderList(path) or [],
        "files": ms.GetFileList(path) or [],
    }


@register(
    "add_storage_items_to_pool",
    "Add file/folder paths from disk (Media Storage) into the current media "
    "pool folder. Returns the created clips.",
    {
        "type": "object",
        "properties": {
            "paths": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["paths"],
    },
)
def add_storage_items_to_pool(resolve, args):
    ms = resolve.GetMediaStorage()
    paths = [os.path.expanduser(p) for p in args["paths"]]
    items = ms.AddItemListToMediaPool(paths) or []
    return {"added": [i.GetName() for i in items], "count": len(items)}
