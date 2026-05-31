#!/usr/bin/env bash
#
# Remove the DaVinci Resolve Lite MCP server symlink from the Scripts menu.
#
set -euo pipefail

LITE="$HOME/Library/Containers/com.blackmagic-design.DaVinciResolveLite/Data/Library/Application Support/Fusion/Scripts/Edit/davinci_mcp_server.py"
STD="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit/davinci_mcp_server.py"

removed=0
for link in "$LITE" "$STD"; do
  if [[ -L "$link" || -f "$link" ]]; then
    rm -f "$link"
    echo "Removed: $link"
    removed=1
  fi
done

[[ "$removed" -eq 0 ]] && echo "Nothing to remove." || true
