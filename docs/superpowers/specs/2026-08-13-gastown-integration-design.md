# Design: Gas Town Integration (Trial)

**Date:** 2026-08-13
**Author:** Compiled with Claude (via `superpowers:brainstorming`)
**Status:** APPROVED (2026-08-13)
**Related:** `~/gt/ai_fitness_trainer/crew/german/CLAUDE.md` (local-only, gitignored — the crew clone
set up 2026-08-12 that this design operates from).

---

## 0. Context and goal

Gas Town (`gastown`, `gt`/`bd` CLIs — [docs.gastownhall.ai](https://docs.gastownhall.ai/)) is a
multi-agent orchestration layer: rigs/crew/polecats for dispatching agent work, beads/convoys for
issue tracking, mayor/deacon/witness/refinery as always-on coordination daemons. A crew clone of
this repo was set up 2026-08-12 at `~/gt/ai_fitness_trainer/crew/german`, separate from the main
Cursor clone this repo normally lives in, specifically to trial Gas Town on top of the project's
existing `superpowers` workflow.

**Why this is a narrow trial, not an adoption decision:** this project is a solo developer plus one
loosely-coupled external collaborator (Alejandro, who owns `cv-service` in his own branch/repo area
and isn't part of this Gas Town setup at all). Gas Town's core value — routing work across a fleet
of agents, cross-rig visibility, attribution across a team — targets multi-agent/multi-person
setups. The motivation here is evaluating the tool, not solving a coordination problem that
currently exists. So the goal is a real but minimal live trial: exercise one genuinely useful piece
(beads/convoy tracking) on one real batch of work, without disrupting how code actually gets
written.

**Explicitly out of scope for this trial:**
- **Polecats** (ephemeral agents doing the actual implementation work) — the coding stays exactly
  where it's always been, in the main Cursor clone, via the normal superpowers cycle.
- **`gt enable`** — a machine-wide toggle (auto-registers every git repo on this Mac as a rig,
  makes Claude Code auto-run `gt prime` on every session start everywhere). Out of scope; Gas Town
  stays confined to the one manually-created crew clone.
- **Full Stack Mode** (the always-on daemon/mayor/deacon/witness/refinery processes) — stopped,
  back to Minimal Mode. Not needed for filing/closing beads.
- **Status-synced tracking** (moving beads through `in_progress` mid-flight via `gt assign`/`sling`)
  — considered and rejected in favor of file-and-forget (below); revisit if the lightweight version
  proves too little signal.

If this trial is useful, the next-tier options above (status-sync, polecats, `gt enable`) are the
natural follow-ups — not decided here.

## 1. Environment (fixed this session, prerequisite to everything else)

`gt doctor` in the crew clone no longer matched yesterday's "clean as of setup" note. Fixed:

- **`bd` binary was never actually installed** (yesterday's CLAUDE.md said binaries came from
  `make install` in the `gastown` repo, but that only produces `gt`; `bd` is a separate repo,
  `github.com/steveyegge/beads`). Installed via `go install github.com/steveyegge/beads/cmd/bd@latest`
  — required Homebrew's keg-only `icu4c@78` on the `CGO_CFLAGS`/`CGO_CXXFLAGS`/`CGO_LDFLAGS`/
  `PKG_CONFIG_PATH` env vars first (the `dolthub/go-icu-regex` cgo dependency doesn't find ICU
  headers otherwise). Binary copied to `~/.local/bin/bd` alongside `gt`.
- **Dolt server (beads' storage backend) wasn't running** — started via `gt dolt start`.
- **`gt doctor --fix`** cleaned up the rest (stale Claude settings file, 5 missing agent identity
  beads, 1 missing rig identity bead, missing post-checkout branch-protection hook) — 90/92 checks
  passing after. The 2 remaining warnings (`global-state` needs `gt enable`, one `.runtime`
  gitignore gap) are left alone, consistent with the scope decisions above.
- `--fix` auto-started the daemon (Full Stack Mode) as a side effect — stopped again afterward
  (`gt daemon stop`) to return to the deliberate Minimal Mode from yesterday's setup.

## 2. Workflow pattern: file-and-forget beads/convoy

- Beads/convoy are filed and closed **from the crew clone**
  (`~/gt/ai_fitness_trainer/crew/german`) — the only checkout with `gt`/`bd` wired up.
- **Actual coding is unaffected** — it happens in the main Cursor clone via the normal superpowers
  cycle (brainstorming → plan → subagent-driven-development, or a direct fix for something small
  enough not to need the full cycle). Gas Town never touches a diff; it sits beside the work, not in
  its path.
- Filing happens **once, up front**, for a known batch of work: one `bd create` per item, one
  `gt convoy create` grouping them under a single trackable unit.
- Each bead is closed (`bd close aft-xxx`) when its fix actually lands on `main`. No status updates
  in between — no `in_progress`, no `gt assign`. The convoy auto-closes once every tracked bead is
  closed.
- What this buys over the current pattern (a "deferred Minor findings" paragraph inside a review
  summary, living only in a memory file / git history): a queryable, persistent record — `bd list`,
  `gt convoy status` — of what a polish pass actually contained and when each piece landed, without
  adding any ceremony to the coding workflow itself.

## 3. This trial's concrete batch

The 5 deferred Minor findings from the 2026-08-12 frontend-design-polish final review become one
convoy, five beads, prefix `aft`:

1. Per-rep score rows never got the display-number/type-scale treatment (only the overall score did
   — the original spec named "overall/rep score", implementation only covered overall).
2. `AppShell` wraps inconsistently between the home page (wrapped once) and the attempt-detail page
   (three separate branches each wrap it independently).
3. Attempt-detail loading/error states aren't width-aligned with the header.
4. The wordmark in `AppShell` isn't a `Link` back to `/`.
5. `STATUS_PILL_CLASSES` has no fallback for an unrecognized status string.

Filing these is this design's own "implementation" — no code changes, just `bd create` × 5 +
`gt convoy create` from the crew clone. The findings themselves get fixed afterward as a separate,
ordinary superpowers cycle (frontend follow-up polish) in the Cursor clone; beads get closed as that
lands.

## 4. Where this is documented going forward

- This spec is the durable record of the pattern and the environment fix.
- Project memory (`project_backend_status` / a new note) gets a pointer so future sessions know the
  crew clone is functional and what pattern to use, without re-deriving it.
- `~/gt/ai_fitness_trainer/crew/german/CLAUDE.md` (local-only) is not modified by this spec — it
  already correctly states day-to-day work happens in the Cursor clone; nothing here contradicts it.
