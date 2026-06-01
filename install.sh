#!/usr/bin/env bash
#
# Install the DaVinci Resolve MCP server into the Resolve "Scripts > Utility"
# menu folder (Utility shows on every page). Source of truth stays in this repo;
# install COPIES the runtime files where Resolve can read them.
#
# Two facts that dictate this design (both verified on DaVinci Resolve Lite):
#   1. Menu scan: Resolve only enumerates the category folders
#      (Utility / Comp / Tool / Edit / Color / Deliver). A custom folder name is
#      NOT shown. So entry scripts must live under a category; helper modules can
#      live in a NON-category folder to stay hidden from the menu.
#   2. Sandbox: Lite cannot follow a symlink whose target is outside its allowed
#      locations (e.g. this repo under ~/Projects) — the script silently never
#      runs. So on Lite we COPY into the container. Re-run after pulling updates.
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO_DIR/src"
ENTRIES=(davinci_mcp_server.py stop_davinci_mcp_server.py)
# Package of helper modules (optional; present once the server is split up).
PKG="resolve_mcp"

LITE_SCRIPTS="$HOME/Library/Containers/com.blackmagic-design.DaVinciResolveLite/Data/Library/Application Support/Fusion/Scripts"
STD_SCRIPTS="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"

if [[ -d "$LITE_SCRIPTS" ]]; then
  SCRIPTS="$LITE_SCRIPTS"; MODE="copy"; echo "Detected DaVinci Resolve Lite (sandboxed) -> COPY install."
elif [[ -d "$STD_SCRIPTS" ]]; then
  SCRIPTS="$STD_SCRIPTS"; MODE="symlink"; echo "Detected DaVinci Resolve (standard install) -> symlink install."
else
  echo "Could not find a DaVinci Resolve Fusion/Scripts folder."
  echo "Open Resolve once so it creates it, then retry."
  exit 1
fi

TARGET_DIR="$SCRIPTS/Utility"          # entry scripts: a scanned category -> appear in menu
MODULES_DIR="$SCRIPTS/MCP/$PKG"        # helper modules: NON-category folder -> hidden from menu
mkdir -p "$TARGET_DIR"

deploy() {  # deploy <src-path> <dest-path>
  local src="$1" dest="$2"
  rm -rf "$dest"
  if [[ "$MODE" == "symlink" ]]; then ln -s "$src" "$dest"; else cp -R "$src" "$dest"; fi
}

# Clean any previous installs of ours (old Edit copies, Utility, stray MCP links).
for dir in "$SCRIPTS/Edit" "$SCRIPTS/Utility"; do
  for name in "${ENTRIES[@]}"; do rm -f "$dir/$name"; done
done

for name in "${ENTRIES[@]}"; do
  [[ -f "$SRC/$name" ]] || { echo "Source not found: $SRC/$name"; exit 1; }
  deploy "$SRC/$name" "$TARGET_DIR/$name"
done

# Ship the helper package (if it exists yet) to the hidden, non-scanned folder.
if [[ -d "$SRC/$PKG" ]]; then
  mkdir -p "$(dirname "$MODULES_DIR")"
  deploy "$SRC/$PKG" "$MODULES_DIR"
  echo "Modules ($PKG) -> $MODULES_DIR  (hidden from menu)"
fi

echo "Installed ($MODE) into: $TARGET_DIR"
for name in "${ENTRIES[@]}"; do echo "  $name"; done
echo
echo "Next:"
echo "  1. Workspace > Scripts > Utility > davinci_mcp_server   (shows on every page)"
echo "  2. Console / logfile prints the MCP endpoint + port."
echo "  3. claude mcp add --transport http davinci http://127.0.0.1:8765/mcp"
echo "  4. Stop:  Workspace > Scripts > Utility > stop_davinci_mcp_server  (or ./stop.sh)"
echo
echo "Logs (Console output is also mirrored here):"
echo "  $HOME/Movies/davinci-resolve-lite-mcp.log   (./logs.sh to tail)"
[[ "$MODE" == "copy" ]] && echo && echo "NOTE: Lite install is a COPY. Re-run ./install.sh after editing the source."
