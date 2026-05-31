#!/usr/bin/env bash
#
# Install the DaVinci Resolve Lite MCP server by symlinking it into the
# Resolve "Scripts > Edit" menu folder. After install, launch it from
# DaVinci Resolve: Workspace > Scripts > Edit > davinci_mcp_server
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_SRC="$REPO_DIR/src/davinci_mcp_server.py"
STOP_SRC="$REPO_DIR/src/stop_davinci_mcp_server.py"

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

for src in "$SERVER_SRC" "$STOP_SRC"; do
  if [[ ! -f "$src" ]]; then
    echo "Source not found: $src"
    exit 1
  fi
done

mkdir -p "$TARGET_DIR"
echo "Symlinked into: $TARGET_DIR"
for src in "$SERVER_SRC" "$STOP_SRC"; do
  link="$TARGET_DIR/$(basename "$src")"
  ln -sf "$src" "$link"
  echo "  $(basename "$link")  ->  $src"
done
echo
echo "Next steps:"
echo "  1. Start:  Workspace > Scripts > Edit > davinci_mcp_server"
echo "  2. The Console (Workspace > Console) prints the MCP endpoint + port."
echo "  3. Register with Claude Code, e.g.:"
echo "       claude mcp add --transport http davinci http://127.0.0.1:8765/mcp"
echo "  4. Stop:   Workspace > Scripts > Edit > stop_davinci_mcp_server"
echo "             (or ./stop.sh, or quit Resolve)"
echo
echo "Resolve hides menu-script output, so logs are written to a file:"
echo "  $HOME/Movies/davinci-resolve-lite-mcp.log"
echo "  View live with:  ./logs.sh"
