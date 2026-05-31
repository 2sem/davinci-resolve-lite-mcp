# Fallbacks — known problems & their workarounds

Each file documents a problem hit while building this project and the fix that
worked, so the gotcha is not rediscovered. Newest at the bottom.

Format per entry: **Symptom → Cause → Fix → Commit**.

| # | Problem | File |
|---|---------|------|
| 01 | Sandbox can't follow symlink to repo (script never runs) | [01-sandbox-symlink.md](01-sandbox-symlink.md) |
| 02 | `fu_stdout has no attribute 'flush'` crash | [02-fu-stdout-flush.md](02-fu-stdout-flush.md) |
| 03 | Menu launch ignored `__name__ == "__main__"` | [03-menu-entrypoint.md](03-menu-entrypoint.md) |
| 04 | Long-running server output not visible in Console | [04-console-buffering.md](04-console-buffering.md) |
| 05 | Connecting to the Resolve object from a menu script | [05-resolve-connection.md](05-resolve-connection.md) |
| 06 | `ExportCurrentFrameAsStill` fails when dir missing | [06-export-makedirs.md](06-export-makedirs.md) |
| 07 | Resolve API calls off the main thread | [07-thread-safety.md](07-thread-safety.md) |
