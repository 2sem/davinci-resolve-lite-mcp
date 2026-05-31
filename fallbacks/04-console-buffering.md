# 04 — Long-running server output not visible in Console

**Symptom**
Short scripts print to the Resolve Console fine, but this continuously-running
server seemed to show nothing.

**Cause (corrected)**
Menu scripts CAN print to the Console — an earlier assumption that they cannot
was wrong. The real risk is that a never-returning script's stdout can sit in a
block buffer, and (separately) the actual blocker here turned out to be other
bugs (sandbox symlink #01, fu_stdout #02) that stopped the script before output.

**Fix**
- Best-effort line-buffering: `getattr(sys.stdout, "reconfigure", None)` then
  `reconfigure(line_buffering=True)` (guarded — see #02).
- `safe_flush()` after each line.
- Belt-and-suspenders: mirror every line to a logfile at
  `~/Movies/davinci-resolve-lite-mcp.log` (sandbox-writable via the movies
  entitlement; real home resolved with `pwd.getpwuid` since the sandbox
  redirects `$HOME`). Override dir with `DAVINCI_MCP_LOG_DIR`. Tail with
  `./logs.sh`.

**Commits** deaa42c, dcbb7c7, 1502c97
