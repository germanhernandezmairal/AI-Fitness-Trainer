# Design: Frontend Follow-Up Polish

**Date:** 2026-08-13
**Author:** Compiled with Claude (via `superpowers:brainstorming`)
**Status:** APPROVED (2026-08-13)
**Related:** `docs/superpowers/specs/2026-08-12-frontend-design-polish-design.md` (the pass this
follows up on — palette/type-scale/AppShell described there are unchanged, this only closes gaps
left by it). Tracked as Gas Town convoy `hq-cv-9wiwh` (beads `aft-92n`/`aft-a64`/`aft-jia`/`aft-lct`/
`aft-a22`) per `docs/superpowers/specs/2026-08-13-gastown-integration-design.md` — see
`[[project-gastown-integration]]` memory.

---

## 0. Context and goal

The 2026-08-12 frontend-design-polish final whole-branch review found 5 Minor findings that were
deliberately deferred rather than fixed in that pass. This is that follow-up: fix all 5, exactly as
listed, no new scope. All 5 are small, independently testable changes to 3 existing files —
no new components, no routing/data-flow changes.

**Explicitly out of scope:** anything not one of the 5 findings below. In particular: no further
visual redesign (the 2026-08-12 pass already resolved that scope question — this is bug-fixing,
not design work), no dark mode, no change to the auth/data model.

## 1. Per-rep score rows get the type-scale treatment (`aft-92n`)

`AttemptResult` (`frontend/src/components/attempt-result.tsx`) already gives the overall score an
eyebrow label + large display number (`text-[11px] font-medium uppercase tracking-wide
text-muted-foreground` / `text-4xl font-bold text-primary`) — the 2026-08-12 spec named this
treatment for "overall/rep score" but only the overall score got it. Each rep row (`<li>` in the
`result.reps.map(...)` list) currently renders `Rep {rep.rep_index}` and `{rep.score} / 100` as
plain, unstyled text in a flex row.

**Fix:** reuse the same two token combos at a scale that fits a list row, not a full card:
- Rep label: `text-[11px] font-medium uppercase tracking-wide text-muted-foreground` (identical
  eyebrow class to "Overall score" — same visual language, no new token).
- Rep score: `text-lg font-bold text-primary` for the number, with the `/ 100` suffix kept smaller
  and muted (`text-xs font-normal text-muted-foreground`), mirroring how the overall score
  de-emphasizes its own `/ 100`.

The row keeps its current flex layout (label left, score right) — this is a typographic fix, not a
layout change (rejected alternative: restructuring each row into a stacked mini-card matching the
overall score's `Card` shape, which would change row height/shape and cross into redesign territory
for something the 2026-08-12 pass already scoped as "polish, not redesign").

## 2 + 3. `AttemptDetailContent` wraps once, at one width (`aft-a64`, `aft-jia`)

`AttemptDetailContent` (`frontend/src/app/attempts/[id]/page.tsx`) currently has three independent
early returns, each calling `<AppShell>` separately:
- `isLoading` → `<AppShell><p className="p-6">Loading...</p></AppShell>`
- `error || !data` → `<AppShell><p className="p-6">Could not load this attempt.</p></AppShell>`
- loaded → `<AppShell><div className="mx-auto max-w-2xl space-y-4 p-6">...</div></AppShell>`

This is both the wrap-inconsistency finding (home page wraps `AppShell` once; this page wraps it
three times) and the width-alignment finding (the loading/error branches use bare `p-6`, missing
the `mx-auto max-w-2xl` the loaded state and the header both use — content visibly shifts width once
data loads).

**Fix:** one refactor resolves both. Compute a `content: ReactNode` variable via the same
loading/error/loaded branching (unchanged conditions, unchanged copy), then return a single
`<AppShell><div className="mx-auto max-w-2xl space-y-4 p-6">{content}</div></AppShell>`. The delete
button and its error `Alert` stay inside the loaded branch only (unchanged behavior — they're not
shown while loading or on a load error, exactly as today).

## 4. AppShell wordmark becomes a `Link` (`aft-lct`)

`AppShell` (`frontend/src/components/app-shell.tsx`) renders `AI Fitness Trainer` as a static
`<span className="text-base font-semibold">`. **Fix:** replace with `next/link`'s `<Link href="/"
className="text-base font-semibold">`, same text and classes, now clickable back to the home page.
No visual change — same size/weight/position — purely adding the missing navigation affordance.

## 5. `STATUS_PILL_CLASSES` gets a fallback (`aft-a22`)

`STATUS_PILL_CLASSES` (`frontend/src/components/attempt-history-list.tsx`) is typed
`Record<AttemptSummary["status"], string>`, so TypeScript already treats all 4 known statuses
(`queued`/`processing`/`completed`/`failed`) as present at compile time — the real gap is a status
value the **backend** sends outside that union at runtime, which TypeScript's type system can't see
or protect against.

**Fix:** add `const DEFAULT_STATUS_PILL_CLASS = "bg-muted text-muted-foreground"` (same neutral
styling already used for `queued`/`processing`) and change the lookup to `STATUS_PILL_CLASSES[
attempt.status] ?? DEFAULT_STATUS_PILL_CLASS`. Being honest about what this actually protects: from
TypeScript's own perspective the `??` is currently unreachable (the indexed type is never
`undefined`), so its unit test must simulate a runtime-only value the type system wouldn't otherwise
allow — a fixture with `status: "unknown" as AttemptSummary["status"]` — rather than pretending
there's a reachable-by-normal-typing code path to exercise.

## Testing

Each of the 5 fixes gets its own test, extending the existing suites for these files (no new test
files):
- Rep row classes: assert the eyebrow/display classes are present on the rendered rep label/score
  (existing `attempt-result.test.tsx`-style query, e.g. by test id or class assertion — implementer's
  call on the exact query, matching how the overall-score treatment is already tested in that
  file if such a test exists, otherwise a straightforward class-presence assertion).
- `AttemptDetailContent` wrap/width: assert a single `AppShell` render (one header) across all three
  states, and that the loading/error containers carry the same `mx-auto max-w-2xl` classes the
  loaded state does.
- Wordmark link: assert the wordmark renders as an `<a href="/">` (or Next `Link` equivalent in
  jsdom), not a bare `<span>`.
- Status-pill fallback: assert an attempt with `status: "unknown" as AttemptSummary["status"]`
  renders `DEFAULT_STATUS_PILL_CLASS`'s classes instead of throwing or rendering `undefined`.

Full frontend unit suite (`npm test`) must stay green; no e2e changes needed (these are visual/
structural fixes to already-covered pages, not new flows).

## Gas Town tracking

No status-sync during implementation (per the file-and-forget pattern in
`docs/superpowers/specs/2026-08-13-gastown-integration-design.md`) — each bead
(`aft-92n`/`aft-a64`/`aft-jia`/`aft-lct`/`aft-a22`) gets closed via `bd close` from the crew clone
once its fix is committed to `main`; the convoy (`hq-cv-9wiwh`) auto-closes once all 5 are closed.
