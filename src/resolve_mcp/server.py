"""MCP JSON-RPC dispatcher, HTTP transport, and entry point."""

import json
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .bridge import ResolveBridge
from .config import (
    CONFIG_PATH,
    DEFAULT_HOST,
    DEFAULT_PORT,
    PORT_PINNED,
    PORT_SCAN_RANGE,
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
)
from .connection import get_resolve
from .logio import LOG_PATH, log, log_file, log_raw, safe_flush
from .tools import TOOLS, ToolError


def log_startup_guide(server_name, version, how, resolve, url, log_path):
    """Emit the full connect-from-Claude guide on launch."""
    add_cmd = f"claude mcp add --transport http davinci {url}"
    if PORT_PINNED:
        src = CONFIG_PATH if CONFIG_PATH else "DAVINCI_MCP_PORT env"
        port_note = f"pinned (from {src}) — will not auto-increment"
    else:
        port_note = "default 8765, auto-increments if busy — see README to pin"
    lines = [
        "",
        "=" * 64,
        f"  {server_name} v{version}",
        "=" * 64,
        f"  Connected to Resolve via : {how}",
        f"  Product                  : {resolve.GetProductName()} "
        f"{resolve.GetVersionString()}",
        f"  MCP endpoint             : {url}",
        f"  Port                     : {port_note}",
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
        "  3) Verify / reconnect:",
        "",
        "       - terminal : claude mcp list   (shows 'davinci')",
        "       - in Claude : type /mcp to view servers and reconnect",
        "         (use /mcp after launching this script if Claude was",
        "          already open, so it picks up the server)",
        "",
        "  3b) (optional) Skip per-tool approval prompts — allow EVERY",
        "      davinci tool at once. Add the bare server name (no tool):",
        "",
        '        - settings.json : "permissions": { "allow": ["mcp__davinci"] }',
        "        - in Claude     : /permissions  then add  mcp__davinci",
        "        - CLI flag       : claude --allowedTools mcp__davinci",
        "",
        "      (mcp__davinci = whole server; mcp__davinci__<tool> = one tool.)",
        "",
        "  4) In Claude Code, just ask it to control Resolve, e.g.:",
        '       "What timeline is open in DaVinci Resolve?"',
        '       "Export the current frame to ~/Movies/frame.png"',
        "",
        "  Other MCP clients: point them at the endpoint above using the",
        "  Streamable HTTP transport (POST JSON-RPC to /mcp).",
        "-" * 64,
        "  Server running. To STOP it without quitting Resolve:",
        "",
        "    Workspace > Scripts > Utility > stop_davinci_mcp_server",
        "    (or run ./stop.sh in a terminal, or quit Resolve)",
        "=" * 64,
        "",
    ]
    for line in lines:
        log_raw(line)  # banner: no per-line timestamp


def _type_ok(value, json_type):
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "boolean":
        return isinstance(value, bool)
    py = {"string": str, "array": list, "object": dict}.get(json_type)
    return isinstance(value, py) if py else True


def _validate_args(name, args, schema):
    """Validate args against the tool's JSON Schema (required / type / enum).

    Raises ToolError with a friendly message on a violation, so a malformed
    call returns a clean tool error instead of a generic internal error.
    """
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in args:
            raise ToolError(f"{name}: missing required argument {req!r}.")
    for key, val in args.items():
        spec = props.get(key)
        if not spec:
            continue  # extra args are tolerated
        types = spec.get("type")
        if types is not None:
            allowed = types if isinstance(types, list) else [types]
            if not any(_type_ok(val, t) for t in allowed):
                raise ToolError(
                    f"{name}: argument {key!r} must be {'/'.join(allowed)}, "
                    f"got {type(val).__name__}."
                )
        if "enum" in spec and val not in spec["enum"]:
            raise ToolError(f"{name}: argument {key!r} must be one of {spec['enum']}.")


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
        arg_str = json.dumps(args, ensure_ascii=False, separators=(",", ":")) if args else "{}"
        if len(arg_str) > 120:
            arg_str = arg_str[:117] + "..."

        def log_call(status, started):
            elapsed_ms = int((time.monotonic() - started) * 1000)
            log(f"[davinci-mcp] {name} {arg_str} -> {status} ({elapsed_ms}ms)")

        spec = TOOLS.get(name)
        if not spec:
            # Logged file-only: this runs on the HTTP handler thread (no bridge
            # job), so we must not write to Resolve's Console from here.
            log_file(f"[davinci-mcp] {name} {arg_str} -> error: Unknown tool (0ms)")
            raise ToolError(f"Unknown tool: {name}")
        handler = spec["handler"]

        try:
            _validate_args(name, args, spec["inputSchema"])
        except ToolError as exc:
            log_file(f"[davinci-mcp] {name} {arg_str} -> error: {exc} (0ms)")
            raise

        # Log on the main thread (inside the queued job) so Console writes share
        # the same single-thread discipline as the Resolve API calls.
        def job(resolve):
            started = time.monotonic()
            try:
                value = handler(resolve, args)
            except ToolError as exc:
                message = str(exc).splitlines()[0] if str(exc) else ""
                log_call(f"error: {message}", started)
                raise
            except Exception as exc:  # noqa: BLE001
                tb_line = traceback.format_exception_only(type(exc), exc)[-1].strip()
                tb_line = tb_line.splitlines()[0] if tb_line else ""
                log_call(f"EXCEPTION: {tb_line}", started)
                raise
            log_call("ok", started)
            return value

        result = self.bridge.call(job)
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

            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
            except (TypeError, ValueError):
                length = 0
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


def start_http_server(host, port, dispatcher, scan=PORT_SCAN_RANGE):
    """Bind, scanning forward from ``port`` if it is in use. Returns (server, port).

    With ``scan == 1`` the port is pinned: bind exactly ``port`` or fail loudly,
    so a configured URL never silently drifts to a neighbouring port.
    """
    span = max(1, scan)
    last_err = None
    for candidate in range(port, port + span):
        try:
            server = ThreadingHTTPServer((host, candidate), make_handler(dispatcher))
            return server, candidate
        except OSError as exc:
            last_err = exc
            continue
    if span == 1:
        raise RuntimeError(
            f"Port {port} is busy and pinned (DAVINCI_MCP_PORT / config 'port' "
            f"is set, so the server will not auto-increment). Free that port or "
            f"choose another: {last_err}"
        )
    raise RuntimeError(f"No free port in {port}..{port + span - 1}: {last_err}")


def run_server(resolve, how):
    bridge = ResolveBridge(resolve)
    dispatcher = MCPDispatcher(bridge)
    scan = 1 if PORT_PINNED else PORT_SCAN_RANGE
    server, port = start_http_server(DEFAULT_HOST, DEFAULT_PORT, dispatcher, scan)
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


def main():
    """Top-level entry, mirroring the reference menu scripts.

    The reference scripts run their logic at module scope and do NOT rely on
    ``__name__ == "__main__"`` (Resolve's menu exec does not guarantee it). So we
    try to connect, and only run the server when a Resolve object is found. When
    imported by the test suite there is no injected ``resolve``, so this is inert.
    """
    # Line-buffer stdout so each line reaches the Resolve Console immediately.
    # Resolve's custom stdout has no reconfigure(), so this is best-effort.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(line_buffering=True)  # Python 3.7+
        except Exception:  # noqa: BLE001
            pass

    resolve, how = get_resolve()
    if resolve is None:
        # Not running inside Resolve (e.g. imported for tests). Stay silent.
        return

    # Immediate Console line, like the reference scripts' "<name> loaded".
    print(f"{SERVER_NAME} loaded")
    safe_flush()

    try:
        run_server(resolve, how)
    except Exception:  # noqa: BLE001
        log("[davinci-mcp] FATAL ERROR:\n" + traceback.format_exc())
        raise
