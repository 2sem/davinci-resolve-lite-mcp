#!/usr/bin/env python
"""Stop the DaVinci Resolve Lite MCP server from inside Resolve.

Launch from DaVinci Resolve: Workspace > Scripts > Edit > stop_davinci_mcp_server

This is a plain localhost HTTP client: it POSTs to the running server's
/shutdown endpoint, so it does not need the Resolve API and can run even while
the server script is busy. Output goes to the Resolve Console.
"""

import os
import sys
import tempfile
import time
import urllib.request


def _bootstrap_sys_path():
    """Put the dir containing the ``resolve_mcp`` package on sys.path (mirrors
    the launcher) so the stop script can reuse the SAME host/port resolution."""
    candidates = []
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(here)                                        # dev: package sibling
        candidates.append(os.path.join(os.path.dirname(here), "MCP"))  # installed: <Scripts>/MCP
    except NameError:
        pass
    home = os.path.expanduser("~")
    candidates.append(os.path.join(
        home, "Library", "Application Support", "Fusion", "Scripts", "MCP"))
    candidates.append(os.path.join(
        home, "Library", "Application Support", "Blackmagic Design",
        "DaVinci Resolve", "Fusion", "Scripts", "MCP"))
    for path in candidates:
        if path and os.path.isdir(os.path.join(path, "resolve_mcp")) and path not in sys.path:
            sys.path.insert(0, path)


def _resolve_host_port():
    """Resolve (host, port) exactly as the server does — env > config file >
    default — so a config-pinned port (outside the default scan window) is still
    reachable. Falls back to env/8765 if the package can't be imported."""
    _bootstrap_sys_path()
    try:
        from resolve_mcp.config import DEFAULT_HOST, DEFAULT_PORT

        return DEFAULT_HOST, DEFAULT_PORT
    except Exception:  # noqa: BLE001
        return (
            os.environ.get("DAVINCI_MCP_HOST", "127.0.0.1"),
            int(os.environ.get("DAVINCI_MCP_PORT", "8765")),
        )


HOST, START_PORT = _resolve_host_port()
SCAN = 20
TIMEOUT = 2

LOG_FILENAME = "davinci-resolve-lite-mcp.log"


def _real_home():
    try:
        import pwd  # noqa: WPS433

        return pwd.getpwuid(os.getuid()).pw_dir
    except Exception:  # noqa: BLE001
        return os.path.expanduser("~")


def _resolve_log_path():
    for directory in (
        os.environ.get("DAVINCI_MCP_LOG_DIR"),
        os.path.join(_real_home(), "Movies"),
        tempfile.gettempdir(),
    ):
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


def safe_flush():
    # Resolve's custom stdout (fu_stdout) has no flush(); guard it.
    flush = getattr(sys.stdout, "flush", None)
    if callable(flush):
        try:
            flush()
        except Exception:  # noqa: BLE001
            pass


def log(message=""):
    """Print to the Console and append to the same logfile as the server."""
    print(message)
    safe_flush()
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}\n")
    except OSError:
        pass


def stop():
    log(f"[davinci-mcp] stop: log file -> {LOG_PATH}")
    for port in range(START_PORT, START_PORT + SCAN):
        url = f"http://{HOST}:{port}/shutdown"
        try:
            req = urllib.request.Request(url, data=b"", method="POST")
            urllib.request.urlopen(req, timeout=TIMEOUT).read()
        except Exception:  # noqa: BLE001  (connection refused / no server here)
            continue
        log(f"[davinci-mcp] Stopped MCP server at {HOST}:{port}")
        return True

    log(
        f"[davinci-mcp] No running MCP server found on "
        f"{HOST}:{START_PORT}..{START_PORT + SCAN - 1}."
    )
    return False


def _inside_resolve():
    import __main__  # noqa: WPS433

    return any(getattr(__main__, name, None) for name in ("resolve", "bmd", "app", "fu"))


def bootstrap():
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(line_buffering=True)  # Python 3.7+
        except Exception:  # noqa: BLE001
            pass
    # Run when launched directly OR from the Resolve menu (Resolve injects
    # scripting globals into __main__). Stays inert on plain test import.
    if __name__ == "__main__" or _inside_resolve():
        print("stop_davinci_mcp_server loaded")
        safe_flush()
        stop()


bootstrap()
