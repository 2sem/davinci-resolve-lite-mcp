#!/usr/bin/env bash
#
# Install the DaVinci Resolve Lite MCP server into the Resolve
# "Scripts > Edit" menu folder. After install, launch it from
# DaVinci Resolve: Workspace > Scripts > Edit > davinci_mcp_server
#
# IMPORTANT: DaVinci Resolve Lite (App Store) is sandboxed. Its sandbox can
# only read a handful of locations (its own container, ~/Movies, user-selected
# files). A symlink that points OUTSIDE those locations (e.g. into this repo
# under ~/Projects) cannot be followed by the sandboxed app, so the script
# silently never runs. Therefore on Lite we COPY the scripts into the app's
# own container, which is always readable. Re-run this script after updating.
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCES=(
  "$REPO_DIR/src/davinci_mcp_server.py"
  "$REPO_DIR/src/stop_davinci_mcp_server.py"
)

LITE_DIR="$HOME/Library/Containers/com.blackmagic-design.DaVinciResolveLite/Data/Library/Application Support/Fusion/Scripts/Edit"
STD_DIR="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit"

if [[ -d "$(dirname "$LITE_DIR")" ]]; then
  TARGET_DIR="$LITE_DIR"
  MODE="copy"   # sandboxed: must live inside the container
  echo "Detected DaVinci Resolve Lite (sandboxed) -> installing by COPY."
elif [[ -d "$(dirname "$STD_DIR")" ]]; then
  TARGET_DIR="$STD_DIR"
  MODE="symlink"   # not sandboxed: symlink so repo edits apply live
  echo "Detected DaVinci Resolve (standard install) -> installing by symlink."
else
  echo "Could not find a DaVinci Resolve scripts folder."
  echo "Open Resolve once so it creates its Fusion/Scripts folder, then retry."
  exit 1
fi

for src in "${SOURCES[@]}"; do
  [[ -f "$src" ]] || { echo "Source not found: $src"; exit 1; }
done

mkdir -p "$TARGET_DIR"
echo "Installed into: $TARGET_DIR"
for src in "${SOURCES[@]}"; do
  dest="$TARGET_DIR/$(basename "$src")"
  rm -f "$dest"
  if [[ "$MODE" == "copy" ]]; then
    cp "$src" "$dest"
  else
    ln -s "$src" "$dest"
  fi
  echo "  $(basename "$dest")"
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
echo "Output prints to the Resolve Console, and is also mirrored to a logfile"
echo "(the server runs continuously, so Console output may buffer):"
echo "  $HOME/Movies/davinci-resolve-lite-mcp.log"
echo "  View live with:  ./logs.sh"
[[ "$MODE" == "copy" ]] && echo && echo "NOTE: Lite install is a COPY. Re-run ./install.sh after you pull updates."
