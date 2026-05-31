#!/usr/bin/env python
"""DaVinci Resolve (Lite) MCP server.

Launch from DaVinci Resolve: Workspace > Scripts > Edit > davinci_mcp_server

This script runs *inside* the Resolve scripting runtime, so it has direct
access to the Resolve API via the global ``resolve`` object. It starts a
zero-dependency HTTP server speaking the Model Context Protocol (MCP) over
JSON-RPC, so an external MCP client (e.g. Claude Code) can drive Resolve.

Design notes
------------
* Stdlib only. Resolve Lite ships no third-party Python packages and the
  sandbox makes pip-into-Resolve fragile, so we depend on nothing.
* The Resolve scripting objects are not assumed thread-safe, so every API
  call is funnelled through a single command queue executed on this script's
  main thread. HTTP handler threads enqueue work and block for the result.
* The Lite app is sandboxed but ships the ``com.apple.security.network.server``
  entitlement, so binding a localhost listening socket is permitted.
"""

import json
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue

SERVER_NAME = "davinci-resolve-lite-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-06-18"

DEFAULT_HOST = os.environ.get("DAVINCI_MCP_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("DAVINCI_MCP_PORT", "8765"))
PORT_SCAN_RANGE = 20  # if DEFAULT_PORT is busy, try the next N ports

# Menu scripts DO print to the Resolve Console. But this server runs forever,
# and a long-running script's stdout can buffer/stay hidden until it exits, so
# we ALSO mirror every line to a logfile (and flush stdout each line). The Lite
# app is sandboxed; ~/Movies is writable from inside it (the assets.movies
# entitlement) and is easy to find, so it is the primary log location.
import tempfile  # noqa: E402
import time  # noqa: E402

LOG_FILENAME = "davinci-resolve-lite-mcp.log"


def _real_home():
    """Real home dir even under the sandbox (HOME is redirected there)."""
    try:
        import pwd  # noqa: WPS433

        return pwd.getpwuid(os.getuid()).pw_dir
    except Exception:  # noqa: BLE001
        return os.path.expanduser("~")


def _resolve_log_path():
    candidates = [
        os.environ.get("DAVINCI_MCP_LOG_DIR"),
        os.path.join(_real_home(), "Movies"),
        tempfile.gettempdir(),
    ]
    for directory in candidates:
        if not directory:
            continue
        try:
            os.makedirs(directory, exist_ok=True)
            path = os.path.join(directory, LOG_FILENAME)
            with open(path, "a", encoding="utf-8"):
                pass
            return path
        except OSError:
            continue
    return os.path.join(tempfile.gettempdir(), LOG_FILENAME)


LOG_PATH = _resolve_log_path()


def log(message=""):
    """Print to the Resolve Console and append to the logfile (timestamped)."""
    print(message)
    sys.stdout.flush()
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            handle.write(f"{stamp}  {message}\n")
    except OSError:
        pass


def log_startup_guide(server_name, version, how, resolve, url, log_path):
    """Emit the full connect-from-Claude guide on launch."""
    add_cmd = f"claude mcp add --transport http davinci {url}"
    lines = [
        "",
        "=" * 64,
        f"  {server_name} v{version}",
        "=" * 64,
        f"  Connected to Resolve via : {how}",
        f"  Product                  : {resolve.GetProductName()} "
        f"{resolve.GetVersionString()}",
        f"  MCP endpoint             : {url}",
        f"  Log file                 : {log_path}",
        "-" * 64,
        "  HOW TO CONNECT FROM CLAUDE CODE",
        "",
        "  1) Keep DaVinci Resolve open with this script running",
        "     (this Console window). Quitting Resolve stops the server.",
        "",
        "  2) In a terminal, register the server with Claude Code:",
        "",
        f"       {add_cmd}",
        "",
        "  3) Verify it is connected:",
        "",
        "       claude mcp list",
        "",
        "  4) In Claude Code, just ask it to control Resolve, e.g.:",
        '       "What timeline is open in DaVinci Resolve?"',
        '       "Export the current frame to ~/Desktop/frame.png"',
        "",
        "  Other MCP clients: point them at the endpoint above using the",
        "  Streamable HTTP transport (POST JSON-RPC to /mcp).",
        "-" * 64,
        "  Server running. To STOP it without quitting Resolve:",
        "",
        "    Workspace > Scripts > Edit > stop_davinci_mcp_server",
        "    (or run ./stop.sh in a terminal, or quit Resolve)",
        "=" * 64,
        "",
    ]
    for line in lines:
        log(line)


# --------------------------------------------------------------------------
# Resolve connection
# --------------------------------------------------------------------------
def get_resolve():
    """Return (resolve, how) or (None, None).

    Resolve injects the scripting objects into the ``__main__`` namespace of a
    menu-launched script (``resolve``, or ``bmd`` / ``app`` / ``fu``), so look
    there first. This mirrors the proven pattern from the reference helper
    ``_resolve_menu_helpers.py``. Fall back to importing DaVinciResolveScript
    for the Console / external use.
    """
    import __main__  # noqa: WPS433

    obj = getattr(__main__, "resolve", None)
    if obj:
        return obj, "__main__.resolve"

    bmd = getattr(__main__, "bmd", None)
    if bmd:
        try:
            obj = bmd.scriptapp("Resolve")
            if obj:
                return obj, "__main__.bmd.scriptapp(Resolve)"
        except Exception:  # noqa: BLE001
            pass

    for global_name in ("app", "fu"):
        host = getattr(__main__, global_name, None)
        get_resolve_fn = getattr(host, "GetResolve", None) if host else None
        if callable(get_resolve_fn):
            try:
                obj = get_resolve_fn()
                if obj:
                    return obj, f"__main__.{global_name}.GetResolve()"
            except Exception:  # noqa: BLE001
                pass

    module_paths = [
        "/Applications/DaVinci Resolve.app/Contents/Resources/Developer/Scripting/Modules",
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
    ]
    try:
        import DaVinciResolveScript as dvr  # noqa: WPS433

        obj = dvr.scriptapp("Resolve")
        if obj:
            return obj, "DaVinciResolveScript.scriptapp(Resolve)"
    except Exception:  # noqa: BLE001
        pass

    for path in module_paths:
        if path not in sys.path:
            sys.path.append(path)
        try:
            import DaVinciResolveScript as dvr  # noqa: WPS433

            obj = dvr.scriptapp("Resolve")
            if obj:
                return obj, f"DaVinciResolveScript from {path}"
        except Exception:  # noqa: BLE001
            continue

    return None, None


# --------------------------------------------------------------------------
# Command queue: all Resolve API calls run on the main script thread
# --------------------------------------------------------------------------
class ResolveBridge:
    """Serializes Resolve API access onto the main script thread."""

    _STOP = object()

    def __init__(self, resolve):
        self.resolve = resolve
        self._queue = Queue()

    def call(self, func):
        """Run ``func(resolve)`` on the main thread, return its result.

        Blocks the calling (HTTP handler) thread until done. Exceptions raised
        by ``func`` are re-raised here.
        """
        done = threading.Event()
        box = {}

        def job():
            try:
                box["result"] = func(self.resolve)
            except Exception as exc:  # noqa: BLE001
                box["error"] = exc
            finally:
                done.set()

        self._queue.put(job)
        done.wait()
        if "error" in box:
            raise box["error"]
        return box.get("result")

    def stop(self):
        self._queue.put(self._STOP)

    def run_forever(self):
        """Main-thread loop. Returns when stop() is called."""
        while True:
            job = self._queue.get()
            if job is self._STOP:
                return
            job()


# --------------------------------------------------------------------------
# Tool implementations
# --------------------------------------------------------------------------
class ToolError(Exception):
    """Raised by tools for user-facing failures."""


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


VALID_PAGES = ("media", "cut", "edit", "fusion", "color", "fairlight", "deliver")


# Each entry: name -> (description, input_schema, handler(resolve, args) -> dict)
def _build_tools():
    tools = {}

    def tool(name, description, schema):
        def register(fn):
            tools[name] = {
                "description": description,
                "inputSchema": schema or {"type": "object", "properties": {}},
                "handler": fn,
            }
            return fn

        return register

    @tool(
        "get_status",
        "Return Resolve product/version and the current project, timeline and page.",
        None,
    )
    def get_status(resolve, args):
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject() if pm else None
        timeline = project.GetCurrentTimeline() if project else None
        return {
            "product": resolve.GetProductName(),
            "version": resolve.GetVersionString(),
            "currentPage": resolve.GetCurrentPage(),
            "project": project.GetName() if project else None,
            "timeline": timeline.GetName() if timeline else None,
        }

    @tool(
        "open_page",
        "Switch the Resolve UI to a page.",
        {
            "type": "object",
            "properties": {
                "page": {"type": "string", "enum": list(VALID_PAGES)},
            },
            "required": ["page"],
        },
    )
    def open_page(resolve, args):
        page = args.get("page")
        if page not in VALID_PAGES:
            raise ToolError(f"page must be one of {VALID_PAGES}")
        ok = resolve.OpenPage(page)
        return {"ok": bool(ok), "page": page}

    @tool(
        "list_projects",
        "List project names in the current database folder.",
        None,
    )
    def list_projects(resolve, args):
        pm = resolve.GetProjectManager()
        if not pm:
            raise ToolError("Project manager unavailable.")
        return {"projects": pm.GetProjectListInCurrentFolder()}

    @tool(
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

    @tool(
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

    @tool(
        "list_timelines",
        "List all timelines in the current project.",
        None,
    )
    def list_timelines(resolve, args):
        project = _require_project(resolve)
        current = project.GetCurrentTimeline()
        current_name = current.GetName() if current else None
        out = []
        for idx in range(1, project.GetTimelineCount() + 1):
            tl = project.GetTimelineByIndex(idx)
            if tl:
                name = tl.GetName()
                out.append({"index": idx, "name": name, "current": name == current_name})
        return {"timelines": out}

    @tool(
        "set_current_timeline",
        "Make the timeline at the given 1-based index current.",
        {
            "type": "object",
            "properties": {"index": {"type": "integer", "minimum": 1}},
            "required": ["index"],
        },
    )
    def set_current_timeline(resolve, args):
        project = _require_project(resolve)
        idx = args["index"]
        tl = project.GetTimelineByIndex(idx)
        if not tl:
            raise ToolError(f"No timeline at index {idx}.")
        if not project.SetCurrentTimeline(tl):
            raise ToolError("SetCurrentTimeline failed.")
        return {"current": tl.GetName()}

    @tool(
        "get_timeline_info",
        "Return name, frame range, start timecode and per-type track counts for the current timeline.",
        None,
    )
    def get_timeline_info(resolve, args):
        tl = _require_timeline(resolve)
        return {
            "name": tl.GetName(),
            "startFrame": tl.GetStartFrame(),
            "endFrame": tl.GetEndFrame(),
            "startTimecode": tl.GetStartTimecode(),
            "currentTimecode": tl.GetCurrentTimecode(),
            "tracks": {
                "video": tl.GetTrackCount("video"),
                "audio": tl.GetTrackCount("audio"),
                "subtitle": tl.GetTrackCount("subtitle"),
            },
        }

    @tool(
        "get_track_items",
        "List clips on a track. trackType one of video/audio/subtitle, 1-based index.",
        {
            "type": "object",
            "properties": {
                "trackType": {"type": "string", "enum": ["video", "audio", "subtitle"]},
                "index": {"type": "integer", "minimum": 1},
            },
            "required": ["trackType", "index"],
        },
    )
    def get_track_items(resolve, args):
        tl = _require_timeline(resolve)
        ttype = args["trackType"]
        idx = args["index"]
        items = tl.GetItemListInTrack(ttype, idx) or []
        out = []
        for it in items:
            out.append(
                {
                    "name": it.GetName(),
                    "start": it.GetStart(),
                    "end": it.GetEnd(),
                    "duration": it.GetDuration(),
                }
            )
        return {"track": f"{ttype}{idx}", "items": out}

    @tool(
        "get_timecode",
        "Get the current playhead timecode of the current timeline.",
        None,
    )
    def get_timecode(resolve, args):
        tl = _require_timeline(resolve)
        return {"timecode": tl.GetCurrentTimecode()}

    @tool(
        "set_timecode",
        "Move the playhead to a timecode (format HH:MM:SS:FF).",
        {
            "type": "object",
            "properties": {"timecode": {"type": "string"}},
            "required": ["timecode"],
        },
    )
    def set_timecode(resolve, args):
        tl = _require_timeline(resolve)
        ok = tl.SetCurrentTimecode(args["timecode"])
        return {"ok": bool(ok), "timecode": tl.GetCurrentTimecode()}

    @tool(
        "add_timeline_marker",
        "Add a marker on the current timeline at a frame offset from the timeline start.",
        {
            "type": "object",
            "properties": {
                "frame": {"type": "integer"},
                "color": {"type": "string", "default": "Blue"},
                "name": {"type": "string", "default": ""},
                "note": {"type": "string", "default": ""},
                "duration": {"type": "integer", "default": 1},
            },
            "required": ["frame"],
        },
    )
    def add_timeline_marker(resolve, args):
        tl = _require_timeline(resolve)
        ok = tl.AddMarker(
            args["frame"],
            args.get("color", "Blue"),
            args.get("name", ""),
            args.get("note", ""),
            args.get("duration", 1),
            "",
        )
        if not ok:
            raise ToolError("AddMarker failed (a marker may already exist at that frame).")
        return {"ok": True, "frame": args["frame"]}

    @tool(
        "list_media_pool",
        "List clips in the current media pool folder (and optionally subfolders).",
        {
            "type": "object",
            "properties": {
                "includeSubfolders": {"type": "boolean", "default": False},
            },
        },
    )
    def list_media_pool(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        folder = mp.GetCurrentFolder()
        if not folder:
            raise ToolError("No current media pool folder.")

        def clip_info(clip):
            return {
                "name": clip.GetName(),
                "type": clip.GetClipProperty("Type"),
                "duration": clip.GetClipProperty("Duration"),
            }

        clips = [clip_info(c) for c in (folder.GetClipList() or [])]
        result = {"folder": folder.GetName(), "clips": clips}
        if args.get("includeSubfolders"):
            result["subfolders"] = [f.GetName() for f in (folder.GetSubFolderList() or [])]
        return result

    @tool(
        "import_media",
        "Import file/folder paths into the current media pool folder.",
        {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["paths"],
        },
    )
    def import_media(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        items = mp.ImportMedia(args["paths"]) or []
        return {"imported": [i.GetName() for i in items], "count": len(items)}

    @tool(
        "append_clips_to_timeline",
        "Append media pool clips (by name, from the current folder) to the current timeline.",
        {
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["names"],
        },
    )
    def append_clips_to_timeline(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        folder = mp.GetCurrentFolder()
        by_name = {c.GetName(): c for c in (folder.GetClipList() or [])}
        wanted = []
        missing = []
        for n in args["names"]:
            if n in by_name:
                wanted.append(by_name[n])
            else:
                missing.append(n)
        if missing:
            raise ToolError(f"Clips not found in current folder: {missing}")
        added = mp.AppendToTimeline(wanted) or []
        return {"appended": len(added), "missing": missing}

    @tool(
        "create_timeline",
        "Create a new empty timeline with the given name.",
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    )
    def create_timeline(resolve, args):
        project = _require_project(resolve)
        mp = project.GetMediaPool()
        tl = mp.CreateEmptyTimeline(args["name"])
        if not tl:
            raise ToolError("CreateEmptyTimeline failed (name may not be unique).")
        return {"created": tl.GetName()}

    @tool(
        "export_current_frame_as_still",
        "Export the current frame of the current timeline to an image file path. "
        "The path must end with a valid image extension (e.g. .jpg, .png, .tif).",
        {
            "type": "object",
            "properties": {"filePath": {"type": "string"}},
            "required": ["filePath"],
        },
    )
    def export_current_frame_as_still(resolve, args):
        project = _require_project(resolve)
        timeline = _require_timeline(resolve)
        path = os.path.expanduser(args["filePath"])
        # Mirror the reference flow (08_export_current_frame): ensure the output
        # directory exists, capture the timecode, then export.
        directory = os.path.dirname(path)
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as exc:
                raise ToolError(f"Could not create directory {directory!r}: {exc}")
        timecode = None
        try:
            timecode = timeline.GetCurrentTimecode()
        except Exception:  # noqa: BLE001
            pass
        ok = project.ExportCurrentFrameAsStill(path)
        if not ok:
            raise ToolError(
                f"ExportCurrentFrameAsStill failed for {path!r}. "
                "Check the path ends with a valid image extension (.jpg/.png/.tif)."
            )
        return {"ok": True, "filePath": path, "timecode": timecode}

    @tool(
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

    @tool(
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

    @tool(
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

    @tool(
        "export_timeline",
        "Export the current timeline to a file. exportType one of: "
        "AAF, EDL, XML(fcpxml), DRT, OTIO. Provide a full filePath.",
        {
            "type": "object",
            "properties": {
                "filePath": {"type": "string"},
                "exportType": {
                    "type": "string",
                    "enum": ["AAF", "EDL", "FCPXML", "DRT", "OTIO"],
                },
            },
            "required": ["filePath", "exportType"],
        },
    )
    def export_timeline(resolve, args):
        tl = _require_timeline(resolve)
        type_map = {
            "AAF": resolve.EXPORT_AAF,
            "EDL": resolve.EXPORT_EDL,
            "FCPXML": resolve.EXPORT_FCPXML_1_8,
            "DRT": resolve.EXPORT_DRT,
            "OTIO": resolve.EXPORT_OTIO,
        }
        etype = type_map.get(args["exportType"])
        ok = tl.Export(args["filePath"], etype, resolve.EXPORT_NONE)
        if not ok:
            raise ToolError("Timeline Export failed.")
        return {"ok": True, "filePath": args["filePath"]}

    return tools


TOOLS = _build_tools()


# --------------------------------------------------------------------------
# MCP / JSON-RPC over HTTP
# --------------------------------------------------------------------------
class MCPDispatcher:
    """Handles MCP JSON-RPC method calls. Stateless."""

    def __init__(self, bridge):
        self.bridge = bridge

    def handle(self, message):
        """Return a JSON-RPC response dict, or None for notifications."""
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}

        # Notifications (no id) get no response.
        is_notification = "id" not in message

        try:
            if method == "initialize":
                result = self._initialize(params)
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": self._list_tools()}
            elif method == "tools/call":
                result = self._call_tool(params)
            elif method in ("notifications/initialized", "notifications/cancelled"):
                return None
            else:
                if is_notification:
                    return None
                return self._error(msg_id, -32601, f"Method not found: {method}")
        except ToolError as exc:
            return self._tool_failure(msg_id, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._error(msg_id, -32603, f"Internal error: {exc}",
                               data=traceback.format_exc())

        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _initialize(self, params):
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }

    def _list_tools(self):
        return [
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            }
            for name, spec in sorted(TOOLS.items())
        ]

    def _call_tool(self, params):
        name = params.get("name")
        args = params.get("arguments") or {}
        spec = TOOLS.get(name)
        if not spec:
            raise ToolError(f"Unknown tool: {name}")
        handler = spec["handler"]
        result = self.bridge.call(lambda r: handler(r, args))
        return {
            "content": [
                {"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}
            ],
            "isError": False,
        }

    @staticmethod
    def _tool_failure(msg_id, text):
        # Tool-level failures are returned as a successful result with isError.
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": f"Error: {text}"}],
                "isError": True,
            },
        }

    @staticmethod
    def _error(msg_id, code, message, data=None):
        err = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return {"jsonrpc": "2.0", "id": msg_id, "error": err}


def make_handler(dispatcher):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):  # quiet; Resolve console stays readable
            pass

        def _send_json(self, payload, status=200):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            # We don't implement the optional SSE GET stream; POST-only is valid.
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            # Control endpoint: stop the server without quitting Resolve.
            if self.path.rstrip("/").endswith("/shutdown"):
                self._send_json({"ok": True, "stopping": SERVER_NAME})
                dispatcher.bridge.stop()
                return

            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            try:
                message = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, UnicodeDecodeError):
                self._send_json(
                    {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "Parse error"}},
                    status=400,
                )
                return

            if isinstance(message, list):  # JSON-RPC batch
                responses = [r for r in (dispatcher.handle(m) for m in message) if r is not None]
                if responses:
                    self._send_json(responses)
                else:
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                return

            response = dispatcher.handle(message)
            if response is None:
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self._send_json(response)

    return Handler


def start_http_server(host, port, dispatcher):
    """Bind, scanning forward from ``port`` if it is in use. Returns (server, port)."""
    last_err = None
    for candidate in range(port, port + PORT_SCAN_RANGE):
        try:
            server = ThreadingHTTPServer((host, candidate), make_handler(dispatcher))
            return server, candidate
        except OSError as exc:
            last_err = exc
            continue
    raise RuntimeError(f"No free port in {port}..{port + PORT_SCAN_RANGE - 1}: {last_err}")


def run_server(resolve, how):
    bridge = ResolveBridge(resolve)
    dispatcher = MCPDispatcher(bridge)
    server, port = start_http_server(DEFAULT_HOST, DEFAULT_PORT, dispatcher)
    url = f"http://{DEFAULT_HOST}:{port}/mcp"

    log_startup_guide(SERVER_NAME, SERVER_VERSION, how, resolve, url, LOG_PATH)

    http_thread = threading.Thread(target=server.serve_forever, name="mcp-http", daemon=True)
    http_thread.start()

    try:
        bridge.run_forever()  # blocks on the main thread, executing Resolve calls
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        log("[davinci-mcp] Server stopped.")


def bootstrap():
    """Top-level entry, mirroring the reference menu scripts.

    The reference scripts (e.g. 02-clone-v1-to-v2.py) run their logic at module
    scope and do NOT rely on ``__name__ == "__main__"`` — Resolve's menu exec
    does not guarantee it. So we do the same: try to connect, and only run the
    server when a Resolve object is found. When imported by the test suite there
    is no injected ``resolve``, so this stays inert.
    """
    # Line-buffer stdout so each line reaches the Resolve Console immediately
    # rather than sitting in a block buffer while the server runs.
    try:
        sys.stdout.reconfigure(line_buffering=True)  # Python 3.7+
    except Exception:  # noqa: BLE001
        pass

    resolve, how = get_resolve()
    if not resolve:
        # Not running inside Resolve (e.g. imported for tests). Stay silent.
        return

    # Immediate Console line, like the reference scripts' "<name> loaded".
    print(f"{SERVER_NAME} loaded")
    sys.stdout.flush()

    try:
        run_server(resolve, how)
    except Exception:  # noqa: BLE001
        log("[davinci-mcp] FATAL ERROR:\n" + traceback.format_exc())
        raise


bootstrap()
