# Gas Town Integration Trial — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** File the 5 deferred frontend-design-polish findings as beads under one convoy, in the Gas
Town crew clone, per `docs/superpowers/specs/2026-08-13-gastown-integration-design.md`.

**Architecture:** CLI-only trial — no application code changes. All commands run from
`~/gt/ai_fitness_trainer/crew/german` (the only checkout with `gt`/`bd` wired to this rig's Dolt-backed
beads database). Each "test" is a verification read (`bd show`, `bd list`, `gt convoy status`)
confirming the write landed with the right fields, mirroring the write/verify rhythm of TDD without
a code test suite to run.

**Tech Stack:** `bd` (beads CLI, `~/.local/bin/bd`), `gt` (Gas Town CLI, `~/.local/bin/gt`), both
already confirmed working (§1 of the design spec).

## Global Constraints

- All commands run with cwd `~/gt/ai_fitness_trainer/crew/german` (routes to the `aft` prefix via
  `.beads/redirect`; confirmed working — `bd list --all` there currently shows only the 4 pre-existing
  agent/rig identity beads, `aft-461`/`aft-4g9`/`aft-bbx`/`aft-rig-ai_fitness_trainer`).
- No code in the main Cursor clone (`/Volumes/Expansion/Software Builder/Web-App
  Projects/AI Fitness Trainer`) is touched by this plan — that repo is not modified by any task here.
- Bead titles/descriptions are taken verbatim from §3 of the design spec — do not paraphrase them
  differently than what's written there, so the bead record matches the spec record exactly.
- This trial follows the spec's "file-and-forget" pattern (§2): beads are filed once, here, with no
  `in_progress` status transition — closing them is future work (when each finding's fix lands on
  `main`), explicitly out of scope for this plan.

---

### Task 1: Silence the `beads.role` warning, then file the 5 beads

**Files:** None (no repo files created/modified — this operates on the Dolt-backed beads database,
not git-tracked files).

**Interfaces:**
- Produces: 5 bead IDs (`aft-xxx`, one per finding) that Task 2 consumes to build the convoy.

- [ ] **Step 1: Configure `beads.role` in the crew clone to silence the warning**

`bd list` in the crew clone currently prints `warning: beads.role not configured (GH#2950)` on every
invocation. This clone is where the human owner works directly (not an automated contributor), so:

```bash
cd ~/gt/ai_fitness_trainer/crew/german
git config beads.role maintainer
```

- [ ] **Step 2: Verify the warning is gone**

Run: `bd list --all`
Expected: same 4 pre-existing beads listed (`aft-461`, `aft-4g9`, `aft-bbx`,
`aft-rig-ai_fitness_trainer`), no `beads.role not configured` warning line above them.

- [ ] **Step 3: File bead 1 — per-rep score rows missing type-scale treatment**

```bash
cd ~/gt/ai_fitness_trainer/crew/german
bd create "Per-rep score rows missing display-number/type-scale treatment" \
  --type bug \
  --priority 3 \
  --description "The 2026-08-12 frontend-design-polish spec named \"overall/rep score\" for the \
display-number/type-scale treatment, but the implementation only applied it to the overall score — \
per-rep score rows in AttemptResult still render as plain text. Deferred Minor finding from that \
pass's final whole-branch review." \
  --silent
```

Capture the printed ID (silent mode prints only the ID) — this is bead 1's ID, needed for Task 2.

- [ ] **Step 4: Verify bead 1**

Run: `bd show <bead-1-id>`
Expected: title, type (`bug`), and description match Step 3 exactly; status `open`.

- [ ] **Step 5: File bead 2 — AppShell wraps inconsistently**

```bash
cd ~/gt/ai_fitness_trainer/crew/german
bd create "AppShell wraps inconsistently between home and attempt-detail pages" \
  --type chore \
  --priority 3 \
  --description "The home page wraps AppShell once; the attempt-detail page wraps it independently \
in three separate branches (loading/error/loaded) instead of wrapping once around all three states. \
Deferred Minor finding from the 2026-08-12 frontend-design-polish final whole-branch review." \
  --silent
```

Capture bead 2's ID.

- [ ] **Step 6: Verify bead 2**

Run: `bd show <bead-2-id>`
Expected: title, type (`chore`), and description match Step 5 exactly; status `open`.

- [ ] **Step 7: File bead 3 — attempt-detail loading/error states not width-aligned**

```bash
cd ~/gt/ai_fitness_trainer/crew/german
bd create "Attempt-detail loading/error states not width-aligned with header" \
  --type bug \
  --priority 3 \
  --description "The attempt-detail page's loading and error states render at a different content \
width than the page's own header, so the layout visibly shifts once data loads. Deferred Minor \
finding from the 2026-08-12 frontend-design-polish final whole-branch review." \
  --silent
```

Capture bead 3's ID.

- [ ] **Step 8: Verify bead 3**

Run: `bd show <bead-3-id>`
Expected: title, type (`bug`), and description match Step 7 exactly; status `open`.

- [ ] **Step 9: File bead 4 — wordmark isn't a Link**

```bash
cd ~/gt/ai_fitness_trainer/crew/german
bd create "AppShell wordmark isn't a Link back to /" \
  --type bug \
  --priority 3 \
  --description "The wordmark text in the shared AppShell header is static text, not a Next.js Link \
to /, so users have no click-to-home affordance from the header. Deferred Minor finding from the \
2026-08-12 frontend-design-polish final whole-branch review." \
  --silent
```

Capture bead 4's ID.

- [ ] **Step 10: Verify bead 4**

Run: `bd show <bead-4-id>`
Expected: title, type (`bug`), and description match Step 9 exactly; status `open`.

- [ ] **Step 11: File bead 5 — STATUS_PILL_CLASSES has no fallback**

```bash
cd ~/gt/ai_fitness_trainer/crew/german
bd create "STATUS_PILL_CLASSES has no fallback for an unrecognized status string" \
  --type bug \
  --priority 3 \
  --description "STATUS_PILL_CLASSES in the attempt-history-list status-pill styling is a lookup \
keyed by known status strings with no default/fallback entry, so an unrecognized status value would \
render with no pill styling applied. Deferred Minor finding from the 2026-08-12 \
frontend-design-polish final whole-branch review." \
  --silent
```

Capture bead 5's ID.

- [ ] **Step 12: Verify bead 5**

Run: `bd show <bead-5-id>`
Expected: title, type (`bug`), and description match Step 11 exactly; status `open`.

- [ ] **Step 13: Verify all 5 together**

Run: `bd list --all` (from `~/gt/ai_fitness_trainer/crew/german`)
Expected: the 4 pre-existing beads plus the 5 new ones (9 total), all 5 new ones showing status
`open`.

---

### Task 2: Create the convoy grouping the 5 beads

**Files:** None (Dolt-backed, town-level `hq-*` convoy record — not git-tracked).

**Interfaces:**
- Consumes: the 5 bead IDs produced by Task 1, Steps 3/5/7/9/11.
- Produces: 1 convoy ID (`hq-xxx`) that Task 3 references when recording the trial's outcome.

- [ ] **Step 1: Create the convoy**

```bash
cd ~/gt/ai_fitness_trainer/crew/german
gt convoy create "Frontend design-polish: deferred findings" \
  <bead-1-id> <bead-2-id> <bead-3-id> <bead-4-id> <bead-5-id> \
  --owned
```

`--owned` marks this caller-managed (per the design spec's file-and-forget pattern — no witness/
refinery auto-registration, since no polecat is doing the work and nothing should be dispatched
automatically).

Capture the printed convoy ID.

- [ ] **Step 2: Verify the convoy**

Run: `gt convoy status <convoy-id>`
Expected: all 5 bead IDs listed as tracked issues, each showing `open`; convoy itself not closed.

---

### Task 3: Record the trial's IDs for future sessions

**Files:**
- Modify: `docs/superpowers/specs/2026-08-13-gastown-integration-design.md` (this repo, the main
  Cursor clone — append an outcome note; this is documentation, not the "no code changes" application
  logic the Global Constraints section refers to).

**Interfaces:** None — this task only records IDs produced by Tasks 1–2, it doesn't produce anything
new for later tasks.

- [ ] **Step 1: Append an outcome section to the design spec**

Add a new `## 5. Trial outcome (2026-08-13)` section at the end of
`docs/superpowers/specs/2026-08-13-gastown-integration-design.md` listing:
- The convoy ID from Task 2, Step 1.
- All 5 bead IDs from Task 1 (with their one-line titles), in the same order as §3.
- One sentence noting they're filed `open`/un-closed, per the file-and-forget pattern — closing them
  is future work tied to the actual frontend-polish fixes landing on `main`, not part of this plan.

- [ ] **Step 2: Verify the section reads correctly**

Read the file back and confirm the appended section is well-formed Markdown, the IDs match what
Tasks 1–2 actually produced (not placeholder text), and it doesn't contradict §2/§3's existing
content.

- [ ] **Step 3: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add docs/superpowers/specs/2026-08-13-gastown-integration-design.md
git commit -m "docs: record Gas Town trial bead/convoy IDs"
```
