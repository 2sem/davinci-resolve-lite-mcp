---
description: Cut a new davinci-resolve-lite-mcp release — branch, bump, PR, and (after merge) tag + GitHub release
---

Run the full release flow for this repo. Follow it in order; do not skip the tag/release step at the end — that step has been missed before.

1. **Determine the next version.** Read `SERVER_VERSION` in `src/resolve_mcp/config.py` for the current version. Look at `CHANGELOG.md`'s `## Unreleased` section for what shipped since the last release, and bump appropriately (new tools/features → minor; fixes only → patch). If `## Unreleased` is empty, ask the user what to include before proceeding — do not invent a release with no content.

2. **Branch.** From a clean `main`, create branch `a.b.c` (version number only, no prefix), e.g. `git checkout -b 0.18.0`.

3. **Bump.** In one commit only:
   - `CHANGELOG.md`: rename `## Unreleased` → `## a.b.c`
   - `src/resolve_mcp/config.py`: `SERVER_VERSION = "a.b.c"`
   - Run `python3 tests/test_server.py` to sanity-check before committing.
   - Commit message: `bump: release a.b.c` — this must be the ONLY commit on this branch.

4. **Push + PR.** Push the branch and open a PR into `main` titled `Release a.b.c`. The PR body must include a full patch note: the complete list of changes since the last release (pull this from the `## a.b.c` CHANGELOG section you just wrote, not a summary). Open the PR in browser.

5. **Wait for explicit merge instruction.** Never merge a release PR without the user explicitly saying so (human review / simulator test gate) — this is non-negotiable regardless of how the release flow was triggered.

6. **On merge instruction: merge, then tag + release — do not stop after the merge.**
   - `gh pr merge <n> --merge --delete-branch`
   - `git checkout main && git pull --ff-only`
   - Create the tag and GitHub release together: `gh release create va.b.c --title "va.b.c — <short summary>" --notes-file <patch-note-file> --target main`. Write the release notes to a scratch file first (a `## Patch note (changes since X.Y.Z)` section mirroring the CHANGELOG entry, plus a `## Notes` section citing the constituent PR(s) and test status) — match the tone/format of prior releases (`gh release view v0.16.0` for reference).
   - Confirm with `gh release view va.b.c` and report the release URL back to the user.

Do not consider the release finished until step 6's tag + release exist — a merged bump commit alone is not a release.
