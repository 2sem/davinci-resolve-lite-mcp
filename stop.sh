#!/usr/bin/env bash
#
# Stop a running DaVinci Resolve Lite MCP server without quitting Resolve.
# Sends a shutdown request to the server's /shutdown endpoint, scanning the
# default port range (same range the server itself scans on startup).
#
set -uo pipefail

HOST="${DAVINCI_MCP_HOST:-127.0.0.1}"
START_PORT="${DAVINCI_MCP_PORT:-8765}"
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
