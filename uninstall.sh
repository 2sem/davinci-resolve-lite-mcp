#!/usr/bin/env bash
#
# Remove the DaVinci Resolve Lite MCP server symlinks from the Scripts menu.
#
set -euo pipefail

NAMES=(davinci_mcp_server.py stop_davinci_mcp_server.py)
BASES=(
  "$HOME/Library/Containers/com.blackmagic-design.DaVinciResolveLite/Data/Library/Application Support/Fusion/Scripts/Edit"
  "$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit"
)

removed=0
for base in "${BASES[@]}"; do
  for name in "${NAMES[@]}"; do
    link="$base/$name"
    if [[ -L "$link" || -f "$link" ]]; then
      rm -f "$link"
      echo "Removed: $link"
      removed=1
    fi
  done
done

[[ "$removed" -eq 0 ]] && echo "Nothing to remove." || true
