#!/usr/bin/env python
"""Stop the DaVinci Resolve Lite MCP server from inside Resolve.

Launch from DaVinci Resolve: Workspace > Scripts > Edit > stop_davinci_mcp_server

This is a plain localhost HTTP client: it POSTs to the running server's
/shutdown endpoint, so it does not need the Resolve API and can run even while
the server script is busy. Output goes to the Resolve Console.
"""

import os
import sys
import urllib.request

HOST = os.environ.get("DAVINCI_MCP_HOST", "127.0.0.1")
START_PORT = int(os.environ.get("DAVINCI_MCP_PORT", "8765"))
SCAN = 20
TIMEOUT = 2


def stop():
    for port in range(START_PORT, START_PORT + SCAN):
        url = f"http://{HOST}:{port}/shutdown"
        try:
            req = urllib.request.Request(url, data=b"", method="POST")
            urllib.request.urlopen(req, timeout=TIMEOUT).read()
        except Exception:  # noqa: BLE001  (connection refused / no server here)
            continue
        print(f"[davinci-mcp] Stopped MCP server at {HOST}:{port}")
        return True

    print(
        f"[davinci-mcp] No running MCP server found on "
        f"{HOST}:{START_PORT}..{START_PORT + SCAN - 1}."
    )
    return False


def main():
    ok = stop()
    sys.stdout.flush()
    return ok


# Resolve runs menu scripts via exec; __name__ is not always "__main__".
if __name__ == "__main__" or globals().get("resolve") is not None:
    main()
