#!/usr/bin/env bash
#
# Install the DaVinci Resolve Lite MCP server by symlinking it into the
# Resolve "Scripts > Edit" menu folder. After install, launch it from
# DaVinci Resolve: Workspace > Scripts > Edit > davinci_mcp_server
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_SRC="$REPO_DIR/src/davinci_mcp_server.py"

# DaVinci Resolve Lite (App Store, sandboxed) stores Fusion scripts in its
# container. The non-Lite/Studio build uses the plain Application Support path.
LITE_DIR="$HOME/Library/Containers/com.blackmagic-design.DaVinciResolveLite/Data/Library/Application Support/Fusion/Scripts/Edit"
STD_DIR="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit"

if [[ -d "$(dirname "$LITE_DIR")" ]]; then
  TARGET_DIR="$LITE_DIR"
  echo "Detected DaVinci Resolve Lite (sandboxed)."
elif [[ -d "$(dirname "$STD_DIR")" ]]; then
  TARGET_DIR="$STD_DIR"
  echo "Detected DaVinci Resolve (standard install)."
else
  echo "Could not find a DaVinci Resolve scripts folder."
  echo "Open Resolve once so it creates its Fusion/Scripts folder, then retry."
  exit 1
fi

if [[ ! -f "$SERVER_SRC" ]]; then
  echo "Server source not found: $SERVER_SRC"
  exit 1
fi

mkdir -p "$TARGET_DIR"
LINK="$TARGET_DIR/davinci_mcp_server.py"
ln -sf "$SERVER_SRC" "$LINK"

echo "Symlinked:"
echo "  $LINK"
echo "  -> $SERVER_SRC"
echo
echo "Next steps:"
echo "  1. In DaVinci Resolve: Workspace > Scripts > Edit > davinci_mcp_server"
echo "  2. The Console (Workspace > Console) prints the MCP endpoint + port."
echo "  3. Register with Claude Code, e.g.:"
echo "       claude mcp add --transport http davinci http://127.0.0.1:8765/mcp"
