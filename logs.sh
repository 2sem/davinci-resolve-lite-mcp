#!/usr/bin/env bash
#
# Tail the DaVinci Resolve Lite MCP server log. Resolve does not reliably show
# menu-script output in its Console, so both scripts mirror everything here.
#
set -uo pipefail

NAME="davinci-resolve-lite-mcp.log"
CANDIDATES=(
  "${DAVINCI_MCP_LOG_DIR:-}/$NAME"
  "$HOME/Movies/$NAME"
  "${TMPDIR:-/tmp}/$NAME"
  "/tmp/$NAME"
)

for path in "${CANDIDATES[@]}"; do
  [[ "$path" == "/$NAME" ]] && continue
  if [[ -f "$path" ]]; then
    echo "Tailing: $path"
    echo "----------------------------------------"
    exec tail -n 50 -f "$path"
  fi
done

echo "No log file found. Looked in:"
printf '  %s\n' "${CANDIDATES[@]}"
echo "Launch the server once (Workspace > Scripts > Edit > davinci_mcp_server)."
exit 1
