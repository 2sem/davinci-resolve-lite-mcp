# 07 — Resolve API called off the main script thread

**Symptom**
An HTTP MCP server uses worker threads per request, but Resolve scripting
objects are not documented as thread-safe; calling them from arbitrary threads
risks undefined behavior.

**Cause**
The script's Resolve objects expect to be used from the script's main thread.
`ThreadingHTTPServer` dispatches each request on its own thread.

**Fix**
Funnel every Resolve API call through a single command queue executed on the
main script thread:
- HTTP handler threads enqueue `func(resolve)` + an `Event`, then block for the
  result.
- The main thread runs `bridge.run_forever()`, pulling jobs and executing them.
- `/shutdown` enqueues a STOP sentinel so `run_forever()` returns and the HTTP
  server is shut down from the main thread (no deadlock).

**Commit** 8194d7e (queue), fba188f (/shutdown)
