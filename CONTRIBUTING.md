# Contributing

Thanks for helping improve **davinci-resolve-lite-mcp**. This guide covers the
two things contributors do most: **adding a tool** and **running the tests**,
plus the project's constraints and release flow.

## Ground rules

- **Standard library only.** The server runs inside DaVinci Resolve's bundled
  Python, which has no `pip` and a sandbox — no third-party packages, ever.
- **Lite-first.** Target the free (Lite) edition. Studio-only API calls must be
  gated at runtime (see [Studio gating](#studio-gating)); they cannot be tested
  on Lite and must never wedge the server when called there.
- **Python 3.9+ syntax floor.** CI runs 3.9 and 3.12. Avoid newer-only syntax
  (`match`/`case`, `dict | dict` union, `X | Y` type hints) — Resolve has
  shipped older interpreters.

## Project layout

```
src/davinci_mcp_server.py        thin launcher (runs at top level from the Resolve menu)
src/resolve_mcp/
  config.py                      version, host/port, protocol constants
  server.py                      MCP dispatcher, arg validation, HTTP server
  bridge.py                      thread-safe command queue (API is not thread-safe)
  connection.py / logio.py       Resolve handle + logging
  tools/
    __init__.py                  register() decorator, TOOLS registry, _TOOL_ORDER
    _helpers.py                  ToolError + shared resolvers (_require_*, _pool_clip, _resolve_clips, ...)
    {status,projects,timelines,tracks,editing,
     color,mediapool,storage,render,gallery}.py   one area module per API surface
tests/
  test_server.py                 offline suite (fake Resolve, no app) — CI-gated
  live_test.py                   live entrypoint: python3 tests/live_test.py [tool ...]
  live/                          one test per tool, grouped by area
```

## Adding a tool

A tool is a single function registered with the `@register` decorator. Adding
one touches **three files**: the area module, the offline count, and the live
test.

### 1. Write the handler

Pick the area module that matches the API surface (e.g. a Gallery call goes in
`tools/gallery.py`). Each module already does `from . import register` and
`from ._helpers import *`. Follow the existing shape:

```python
@register(
    "set_gallery_still_label",
    "Set the label of a gallery still by index (1-based).",
    {
        "type": "object",
        "properties": {
            "index": {"type": "integer"},
            "label": {"type": "string"},
        },
        "required": ["index", "label"],
    },
)
def set_gallery_still_label(resolve, args):
    album = _current_still_album(resolve)        # use _helpers, don't re-derive
    still = _stills_by_index(album, [args["index"]])[0]
    album.SetLabel(still, args["label"])
    return {"ok": True}
```

Conventions:

- **Signature is `(resolve, args)`.** `resolve` is the Resolve handle; `args` is
  the validated input dict.
- **Validation is declarative.** The dispatcher enforces `required`, `type`, and
  `enum` from your `inputSchema` *before* the handler runs — don't re-check them
  by hand. Just declare the schema correctly.
- **Raise `ToolError(msg)` for clean failures** (bad input, API returned false).
  It becomes a structured MCP error instead of a stack trace.
- **Reuse `_helpers`.** Need the current project/timeline/gallery? Use
  `_require_project` / `_require_timeline` / `_require_gallery`. Need a media-pool
  clip by name or id? `_pool_clip(resolve, name=..., clip_id=...)`. Multiple
  clips? `_resolve_clips(resolve, names, ids)`. Don't reimplement these.
- **Return a JSON-serializable dict.** `{"ok": True}` for actions; `{...}` of
  data for queries. List tools that expose clips should include each clip's
  `id` so callers can address it later.

`@register` alone is enough to wire the tool — `_TOOL_ORDER` is for display
order only and auto-appends unlisted tools. Add your name to `_TOOL_ORDER` in
`tools/__init__.py` if you care where it shows in `tools/list`; otherwise skip it.

> A name listed in `_TOOL_ORDER` that is never registered fails an `assert` at
> import (catches a renamed/typo'd handler). Don't add the name to the list
> before the `@register` exists.

### 2. Bump the offline count

`tests/test_server.py` asserts the exact registry size:

```python
EXPECTED_TOOL_COUNT = 149   # increment when you add/remove a tool
```

Update this number. The offline suite is what CI runs, so a wrong count fails
the build.

### 3. Add a live test

Add one test per tool in the matching `tests/live/{area}.py`. **The test name
must equal the tool name** — that's how `python3 tests/live_test.py <tool>` runs
just yours.

```python
@test("set_gallery_still_label")
def _():
    # must be reversible: leave Resolve as you found it
    need(call("get_gallery_stills_count")["count"] >= 0)
```

Helpers available from `tests.live`: `call(tool, **kw)` (asserts success and
returns the result), `err(tool, **kw)` (asserts a clean failure), `need(cond,
msg)` (assertion), `Skip` / `skip_if(...)` (skip on a known env-flaky
signature), `goto_scratch()` (switch to the disposable test timeline). **Tests
must be reversible** — operate on the scratch timeline / temp folders and undo
any mutation. Never touch the user's real timeline.

## Studio gating

Studio-only calls pop an upgrade modal on Lite that wedges UI automation. Gate
them at the top of the handler:

```python
def detect_scene_cuts(resolve, args):
    _require_studio(resolve)   # raises ToolError on Lite before any API call
    ...
```

The corresponding live test should `skip` on Lite rather than fail.

## Running the tests

```bash
# Offline — no DaVinci Resolve needed (fake Resolve). Run before every PR.
python3 tests/test_server.py

# Live — needs Resolve open with the server running
#   (Workspace > Scripts > Utility > davinci_mcp_server)
python3 tests/live_test.py                      # all tools
python3 tests/live_test.py set_timecode         # just one (test name == tool name)
```

CI (`.github/workflows/test.yml`) runs the **offline** suite on every push and
PR across Python 3.9 and 3.12. The live suite needs a running Resolve and stays
manual.

## Install for development

`./install.sh` symlinks (Studio) or copies (Lite — the sandbox can't follow
symlinks into `~/Projects`) the package into Resolve's Scripts folder. After
editing, restart the server from the Resolve menu.

## Release flow

1. Land your change via PR to `main` (CI must be green).
2. Update `CHANGELOG.md` (newest version on top, `### Added` / `### Fixed`
   sections) and bump `SERVER_VERSION` in `src/resolve_mcp/config.py`.
3. Tag and publish: `git tag -a vX.Y.Z` + `gh release create vX.Y.Z`.

Publishing the GitHub release (step 3) triggers `.github/workflows/publish.yml`,
which builds and uploads the package to PyPI via
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC — no
stored token). The package version comes from `SERVER_VERSION`
(`pyproject.toml` reads it dynamically), so step 2 is what actually sets the
PyPI version too. **One-time setup required** before the first release after
this is added: register the project on PyPI and add this repo's
`.github/workflows/publish.yml` (environment `pypi`) as a trusted publisher —
see the docs link above. Until that's done, `publish.yml` will fail; it does
not block the GitHub release itself.

Keep `README.md` and `docs/TOOLS.md` in sync with the tool count when you add or
remove a tool.

## Documented gotchas

Before debugging anything that smells environmental (sandbox, stdout, thread
safety, marker frames), skim `fallbacks/` — every hard-won quirk is written up
there. If you hit a new one, add a numbered note.
