#!/usr/bin/env bash
#
# Stop a running DaVinci Resolve Lite MCP server without quitting Resolve.
# Sends a shutdown request to the server's /shutdown endpoint, scanning a port
# window from the resolved start port (same resolution the server uses).
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve host/port the same way the server does — env > config file > default —
# by reusing resolve_mcp.config, so a config-pinned port (which can sit outside
# the old default scan window) is still reachable. Falls back to env/defaults if
# python3 or the package is unavailable.
read -r HOST START_PORT < <(
  DAVINCI_MCP_SRC="$SCRIPT_DIR/src" python3 - <<'PY' 2>/dev/null
import os, sys
home = os.path.expanduser("~")
for p in (
    os.environ.get("DAVINCI_MCP_SRC"),
    os.path.join(home, "Library", "Application Support", "Fusion", "Scripts", "MCP"),
    os.path.join(home, "Library", "Application Support", "Blackmagic Design",
                 "DaVinci Resolve", "Fusion", "Scripts", "MCP"),
):
    if p and os.path.isdir(os.path.join(p, "resolve_mcp")):
        sys.path.insert(0, p)
        break
try:
    from resolve_mcp.config import DEFAULT_HOST, DEFAULT_PORT
    print(DEFAULT_HOST, DEFAULT_PORT)
except Exception:
    print(os.environ.get("DAVINCI_MCP_HOST", "127.0.0.1"),
          os.environ.get("DAVINCI_MCP_PORT", "8765"))
PY
)
HOST="${HOST:-${DAVINCI_MCP_HOST:-127.0.0.1}}"
START_PORT="${START_PORT:-${DAVINCI_MCP_PORT:-8765}}"
SCAN=20

stopped=0
for ((port = START_PORT; port < START_PORT + SCAN; port++)); do
  url="http://$HOST:$port/shutdown"
  if curl -fsS -m 2 -X POST "$url" -o /dev/null 2>/dev/null; then
    echo "Stopped MCP server at $HOST:$port"
    stopped=1
    break
  fi
done

if [[ "$stopped" -eq 0 ]]; then
  echo "No running MCP server found on $HOST:$START_PORT..$((START_PORT + SCAN - 1))."
  exit 1
fi
