"""Render Resolve MCP tools."""

import os

from . import register
from ._helpers import *


@register(
    "get_render_presets",
    "List available render presets and current render format/codec.",
    None,
)
def get_render_presets(resolve, args):
    project = _require_project(resolve)
    return {
        "renderPresets": project.GetRenderPresetList(),
        "currentFormatAndCodec": project.GetCurrentRenderFormatAndCodec(),
    }


@register(
    "render_current_timeline",
    "Queue a render job for the current timeline and start rendering. "
    "Optionally set a render preset and an output directory/filename first.",
    {
        "type": "object",
        "properties": {
            "preset": {"type": "string"},
            "targetDir": {"type": "string"},
            "customName": {"type": "string"},
        },
    },
)
def render_current_timeline(resolve, args):
    project = _require_project(resolve)
    _require_timeline(resolve)
    if args.get("preset"):
        if not project.LoadRenderPreset(args["preset"]):
            raise ToolError(f"Render preset {args['preset']!r} not found.")
    settings = {}
    if args.get("targetDir"):
        settings["TargetDir"] = args["targetDir"]
    if args.get("customName"):
        settings["CustomName"] = args["customName"]
    if settings and not project.SetRenderSettings(settings):
        raise ToolError("SetRenderSettings failed.")
    job_id = project.AddRenderJob()
    if not job_id:
        raise ToolError("AddRenderJob failed.")
    started = project.StartRendering([job_id], False)
    return {"jobId": job_id, "started": bool(started)}


@register(
    "add_render_job",
    "Queue a render job for the current timeline WITHOUT starting it (for "
    "building a batch queue). Optionally set a preset and output "
    "directory/filename first. Returns the new job id.",
    {
        "type": "object",
        "properties": {
            "preset": {"type": "string"},
            "targetDir": {"type": "string"},
            "customName": {"type": "string"},
        },
    },
)
def add_render_job(resolve, args):
    project = _require_project(resolve)
    _require_timeline(resolve)
    if args.get("preset") and not project.LoadRenderPreset(args["preset"]):
        raise ToolError(f"Render preset {args['preset']!r} not found.")
    settings = {}
    if args.get("targetDir"):
        settings["TargetDir"] = os.path.expanduser(args["targetDir"])
    if args.get("customName"):
        settings["CustomName"] = args["customName"]
    if settings and not project.SetRenderSettings(settings):
        raise ToolError("SetRenderSettings failed.")
    job_id = project.AddRenderJob()
    if not job_id:
        raise ToolError("AddRenderJob failed.")
    return {"ok": True, "jobId": job_id}


@register(
    "get_render_status",
    "Return render-in-progress flag and the render job queue with statuses.",
    None,
)
def get_render_status(resolve, args):
    project = _require_project(resolve)
    jobs = project.GetRenderJobList() or []
    statuses = []
    for job in jobs:
        jid = job.get("JobId")
        statuses.append({"jobId": jid, "status": project.GetRenderJobStatus(jid)})
    return {
        "rendering": bool(project.IsRenderingInProgress()),
        "jobs": statuses,
    }


@register(
    "stop_rendering",
    "Stop any render currently in progress.",
    None,
)
def stop_rendering(resolve, args):
    project = _require_project(resolve)
    project.StopRendering()
    return {"ok": True, "rendering": bool(project.IsRenderingInProgress())}


@register(
    "delete_render_job",
    "Delete a render job from the queue by job id. Omit 'jobId' to clear the "
    "entire queue.",
    {
        "type": "object",
        "properties": {"jobId": {"type": "string"}},
    },
)
def delete_render_job(resolve, args):
    project = _require_project(resolve)
    job_id = args.get("jobId")
    if job_id == "":
        raise ToolError("jobId is empty; omit it entirely to clear the whole queue.")
    if job_id is not None:
        if not project.DeleteRenderJob(job_id):
            raise ToolError(f"DeleteRenderJob({job_id!r}) failed.")
        return {"ok": True, "deleted": job_id}
    if not project.DeleteAllRenderJobs():
        raise ToolError("DeleteAllRenderJobs failed.")
    return {"ok": True, "deleted": "all"}


@register(
    "get_render_formats",
    "List available render formats (format -> file extension). Pass 'format' "
    "to instead list codecs (description -> codec name) for that format.",
    {
        "type": "object",
        "properties": {"format": {"type": "string"}},
    },
)
def get_render_formats(resolve, args):
    project = _require_project(resolve)
    fmt = args.get("format")
    if fmt:
        return {"format": fmt, "codecs": project.GetRenderCodecs(fmt) or {}}
    return {"formats": project.GetRenderFormats() or {}}


@register(
    "set_render_format_codec",
    "Set the current render format (e.g. 'mp4', 'mov') and codec (e.g. "
    "'H264', 'H265'). Use get_render_formats to discover valid values.",
    {
        "type": "object",
        "properties": {
            "format": {"type": "string"},
            "codec": {"type": "string"},
        },
        "required": ["format", "codec"],
    },
)
def set_render_format_codec(resolve, args):
    project = _require_project(resolve)
    if not project.SetCurrentRenderFormatAndCodec(args["format"], args["codec"]):
        raise ToolError(
            f"SetCurrentRenderFormatAndCodec({args['format']!r}, "
            f"{args['codec']!r}) failed (invalid format/codec)."
        )
    return {"ok": True, **project.GetCurrentRenderFormatAndCodec()}


@register(
    "import_render_preset",
    "Import a render preset from a file and set it as the current render "
    "preset.",
    {"type": "object", "properties": {"filePath": {"type": "string"}}, "required": ["filePath"]},
)
def import_render_preset(resolve, args):
    path = os.path.expanduser(args["filePath"])
    if not os.path.exists(path):
        raise ToolError(f"File not found: {path}")
    if not resolve.ImportRenderPreset(path):
        raise ToolError("ImportRenderPreset failed.")
    return {"ok": True, "filePath": path}


@register(
    "export_render_preset",
    "Export a USER render preset (by name) to a path. Factory presets "
    "cannot be exported; save one with save_render_preset first.",
    {"type": "object", "properties": {
        "name": {"type": "string"}, "filePath": {"type": "string"}},
     "required": ["name", "filePath"]},
)
def export_render_preset(resolve, args):
    path = os.path.expanduser(args["filePath"])
    directory = os.path.dirname(path)
    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as exc:
            raise ToolError(f"Could not create directory {directory!r}: {exc}")
    if not resolve.ExportRenderPreset(args["name"], path):
        raise ToolError(f"ExportRenderPreset({args['name']!r}) failed (unknown preset?).")
    return {"ok": True, "filePath": path, "preset": args["name"]}


@register(
    "save_render_preset",
    "Save the current render settings as a new preset.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def save_render_preset(resolve, args):
    project = _require_project(resolve)
    if not project.SaveAsNewRenderPreset(args["name"]):
        raise ToolError("SaveAsNewRenderPreset failed (name not unique?).")
    return {"ok": True, "preset": args["name"]}


@register(
    "delete_render_preset",
    "Delete a render preset by name.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def delete_render_preset(resolve, args):
    project = _require_project(resolve)
    if not project.DeleteRenderPreset(args["name"]):
        raise ToolError("DeleteRenderPreset failed.")
    return {"ok": True, "deleted": args["name"]}


@register(
    "load_render_preset",
    "Set a render preset (by name) as the current render preset.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def load_render_preset(resolve, args):
    project = _require_project(resolve)
    if not project.LoadRenderPreset(args["name"]):
        raise ToolError(f"Render preset {args['name']!r} not found.")
    return {"ok": True, "preset": args["name"]}


@register(
    "get_render_mode",
    "Get the render mode: 0 = individual clips, 1 = single clip.",
    None,
)
def get_render_mode(resolve, args):
    project = _require_project(resolve)
    return {"renderMode": project.GetCurrentRenderMode()}


@register(
    "set_render_mode",
    "Set the render mode: 0 = individual clips, 1 = single clip.",
    {"type": "object", "properties": {"mode": {"type": "integer", "enum": [0, 1]}}, "required": ["mode"]},
)
def set_render_mode(resolve, args):
    project = _require_project(resolve)
    if not project.SetCurrentRenderMode(args["mode"]):
        raise ToolError("SetCurrentRenderMode failed.")
    return {"ok": True, "renderMode": args["mode"]}


@register(
    "get_render_resolutions",
    "List render resolutions valid for a format + codec (or all if omitted).",
    {"type": "object", "properties": {"format": {"type": "string"}, "codec": {"type": "string"}}},
)
def get_render_resolutions(resolve, args):
    project = _require_project(resolve)
    if args.get("format") and args.get("codec"):
        res = project.GetRenderResolutions(args["format"], args["codec"])
    else:
        res = project.GetRenderResolutions()
    return {"resolutions": res or []}


@register(
    "get_quick_export_presets",
    "List available Quick Export presets.",
    None,
)
def get_quick_export_presets(resolve, args):
    project = _require_project(resolve)
    return {"presets": project.GetQuickExportRenderPresets() or []}


@register(
    "quick_export",
    "Quick Export the current timeline with a preset (from "
    "get_quick_export_presets). Optional targetDir / customName.",
    {"type": "object", "properties": {
        "preset": {"type": "string"},
        "targetDir": {"type": "string"},
        "customName": {"type": "string"}},
     "required": ["preset"]},
)
def quick_export(resolve, args):
    project = _require_project(resolve)
    _require_timeline(resolve)
    params = {}
    if args.get("targetDir"):
        params["TargetDir"] = os.path.expanduser(args["targetDir"])
    if args.get("customName"):
        params["CustomName"] = args["customName"]
    status = project.RenderWithQuickExport(args["preset"], params)
    if isinstance(status, str):
        raise ToolError(f"RenderWithQuickExport failed: {status}")
    return {"ok": True, "status": status}
