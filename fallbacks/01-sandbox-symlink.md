# 01 — Sandbox can't follow a symlink to the repo

**Symptom**
Launching the menu script produced nothing at all: no Console output, no
logfile. Short reference scripts (in `~/Movies/...`) worked fine.

**Cause**
DaVinci Resolve Lite (App Store) is sandboxed. Its entitlements grant read
access only to: its own container, `~/Movies` (`assets.movies.read-write`), and
files the user picks interactively. The installer symlinked the menu script to
the clone under `~/Projects/...`, which is NOT entitled. The sandbox can see the
symlink but is denied when following it to the real file, so Resolve never
loads/executes the script. The user's own scripts work only because they live
in the entitled `~/Movies`.

**Fix**
`install.sh` **copies** the scripts into the app container's `Fusion/Scripts`
(always readable inside the sandbox) on Lite; it symlinks only on the
non-sandboxed Studio build. Re-run `install.sh` after pulling updates. Same rule
applies to any path the tools touch (exports/imports must be under `~/Movies` or
a granted location).

**Re-confirmed (2026-06-01):** symlinking the entry script into
`Scripts/Utility` with the target in `~/Projects` was tested directly — it
appeared in the menu but produced no Console output and no logfile (sandbox
denied reading the target). Copy into the container worked. A symlink whose
target is in an entitled location (`~/Movies`) would also work.

**Related menu-scan fact:** Resolve only enumerates the category folders
(`Utility / Comp / Tool / Edit / Color / Deliver`). A custom folder such as
`Scripts/MCP` is NOT shown in the menu — useful as a hiding spot for helper
modules, but entry scripts must live under a category. We use `Utility` (shows
on every page).

**Commit** b2385e1 (orig), + installer moved to Utility + module-hiding folder
