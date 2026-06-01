"""Projects Resolve MCP tools."""

import os

from . import register
from ._helpers import *


@register(
    "list_projects",
    "List project names in the current database folder.",
    None,
)
def list_projects(resolve, args):
    pm = resolve.GetProjectManager()
    if not pm:
        raise ToolError("Project manager unavailable.")
    return {"projects": pm.GetProjectListInCurrentFolder()}


@register(
    "load_project",
    "Load a project by name from the current database folder.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def load_project(resolve, args):
    pm = resolve.GetProjectManager()
    project = pm.LoadProject(args["name"]) if pm else None
    if not project:
        raise ToolError(f"Could not load project {args['name']!r}.")
    return {"loaded": project.GetName()}


@register(
    "get_project_info",
    "Return name, framerate, resolution and timeline count for the current project.",
    None,
)
def get_project_info(resolve, args):
    project = _require_project(resolve)
    return {
        "name": project.GetName(),
        "framerate": project.GetSetting("timelineFrameRate"),
        "resolutionWidth": project.GetSetting("timelineResolutionWidth"),
        "resolutionHeight": project.GetSetting("timelineResolutionHeight"),
        "timelineCount": project.GetTimelineCount(),
    }


@register(
    "export_project",
    "Export (back up) the current project to a .drp file at the given path.",
    {
        "type": "object",
        "properties": {"filePath": {"type": "string"}},
        "required": ["filePath"],
    },
)
def export_project(resolve, args):
    pm = resolve.GetProjectManager()
    project = _require_project(resolve)
    path = os.path.expanduser(args["filePath"])
    directory = os.path.dirname(path)
    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            raise ToolError(f"Could not create directory {directory!r}: {exc}")
    if not pm.ExportProject(project.GetName(), path):
        raise ToolError("ExportProject failed.")
    return {"ok": True, "filePath": path, "project": project.GetName()}


@register(
    "import_project",
    "Import a project from a .drp file. Optional 'name' for the imported "
    "project.",
    {
        "type": "object",
        "properties": {
            "filePath": {"type": "string"},
            "name": {"type": "string"},
        },
        "required": ["filePath"],
    },
)
def import_project(resolve, args):
    pm = resolve.GetProjectManager()
    path = os.path.expanduser(args["filePath"])
    if not os.path.exists(path):
        raise ToolError(f"File not found: {path}")
    ok = pm.ImportProject(path, args["name"]) if args.get("name") else pm.ImportProject(path)
    if not ok:
        raise ToolError("ImportProject failed.")
    return {"ok": True, "filePath": path}


@register(
    "restore_project",
    "Restore a project from a file path (e.g. a .dra archive folder or .drp). "
    "Optional 'name' for the restored project.",
    {"type": "object", "properties": {
        "filePath": {"type": "string"}, "name": {"type": "string"}},
     "required": ["filePath"]},
)
def restore_project(resolve, args):
    pm = resolve.GetProjectManager()
    path = os.path.expanduser(args["filePath"])
    if not os.path.exists(path):
        raise ToolError(f"Path not found: {path}")
    ok = pm.RestoreProject(path, args["name"]) if args.get("name") else pm.RestoreProject(path)
    if not ok:
        raise ToolError("RestoreProject failed.")
    return {"ok": True, "filePath": path}


@register(
    "get_project_presets",
    "List the current project's presets.",
    None,
)
def get_project_presets(resolve, args):
    project = _require_project(resolve)
    return {"presets": project.GetPresetList() or []}


@register(
    "set_project_preset",
    "Apply a named project preset to the current project.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def set_project_preset(resolve, args):
    project = _require_project(resolve)
    if not project.SetPreset(args["name"]):
        raise ToolError(f"SetPreset({args['name']!r}) failed.")
    return {"ok": True, "preset": args["name"]}


@register(
    "get_setting",
    "Read a project or timeline setting. scope = 'project' (default) or "
    "'timeline'. Omit 'name' to return all settings as a dict.",
    {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": ["project", "timeline"], "default": "project"},
            "name": {"type": "string"},
        },
    },
)
def get_setting(resolve, args):
    scope = args.get("scope", "project")
    target = _require_project(resolve) if scope == "project" else _require_timeline(resolve)
    name = args.get("name")
    value = target.GetSetting(name) if name else target.GetSetting()
    return {"scope": scope, "name": name, "value": value}


@register(
    "set_setting",
    "Set a project or timeline setting. scope = 'project' (default) or "
    "'timeline'. Both name and value are strings.",
    {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": ["project", "timeline"], "default": "project"},
            "name": {"type": "string"},
            "value": {"type": "string"},
        },
        "required": ["name", "value"],
    },
)
def set_setting(resolve, args):
    scope = args.get("scope", "project")
    target = _require_project(resolve) if scope == "project" else _require_timeline(resolve)
    ok = target.SetSetting(args["name"], str(args["value"]))
    if not ok:
        raise ToolError(
            f"SetSetting failed for {scope} {args['name']!r}="
            f"{args['value']!r} (unknown key or invalid value)."
        )
    return {"ok": True, "scope": scope, "name": args["name"], "value": args["value"]}


@register(
    "save_project",
    "Save the current project (persists changes to disk).",
    None,
)
def save_project(resolve, args):
    pm = resolve.GetProjectManager()
    if not pm or not pm.SaveProject():
        raise ToolError("SaveProject failed.")
    return {"ok": True}


@register(
    "create_project",
    "Create and open a new project with a unique name.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def create_project(resolve, args):
    pm = resolve.GetProjectManager()
    project = pm.CreateProject(args["name"]) if pm else None
    if not project:
        raise ToolError(f"CreateProject({args['name']!r}) failed (name not unique?).")
    return {"ok": True, "created": project.GetName()}


@register(
    "close_project",
    "Close the current project WITHOUT saving. Call save_project first to "
    "keep changes.",
    None,
)
def close_project(resolve, args):
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject() if pm else None
    if not project:
        raise ToolError("No project is open.")
    name = project.GetName()
    if not pm.CloseProject(project):
        raise ToolError("CloseProject failed.")
    return {"ok": True, "closed": name}
