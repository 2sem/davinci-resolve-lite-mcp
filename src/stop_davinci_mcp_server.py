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

HOST = os.environ.get("DAVINCI_MCP_HOST", "127.0.0.1")
START_PORT = int(os.environ.get("DAVINCI_MCP_PORT", "8765"))
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


def log(message=""):
    """Print to the Console and append to the same logfile as the server."""
    print(message)
    sys.stdout.flush()
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


def main():
    return stop()


# Resolve runs menu scripts via exec; __name__ is not always "__main__".
if __name__ == "__main__" or globals().get("resolve") is not None:
    main()
