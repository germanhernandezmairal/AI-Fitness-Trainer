# Design: Frontend Design Polish Pass

**Date:** 2026-08-12
**Author:** Compiled with Claude (via `superpowers:brainstorming`, using the visual companion for
palette selection)
**Status:** APPROVED (2026-08-12)
**Related:** `docs/superpowers/specs/2026-08-04-frontend-design.md` (frontend-v1 design this pass
polishes — pages/components/auth/error-handling described there are unchanged), frontend-v1 PR #2
(merged 2026-08-07, `d511efd`).

---

## 0. Context and goal

Frontend-v1 shipped functional but visually plain: pure shadcn/ui defaults (a zero-chroma grayscale
palette — every color token is `oklch(_ 0 0)`), Geist loaded but with no real type scale, no shared
site chrome (header/nav) anywhere, and a raw unstyled native `<input type="file">` on the upload
form. Per the work split agreed with Alejandro (2026-08-11, see `project_backend_status` memory):
Alejandro owns `cv-service` accuracy work, the user owns frontend design. This is that piece.

**Scope decision (resolved first, before any visual direction):** a **polish pass**, not a full
visual/IA redesign. The existing page structure and user flows (login/register → home with
upload+history → attempt detail with poll/result/delete) are correct and already tested; this pass
changes how they look, not what they do or how they're organized.

**Explicitly out of scope:**
- Dark mode. The `.dark` CSS class/tokens already exist in `globals.css` (unused) and are left as-is
  for a later pass.
- Any change to routing, page structure, data flow, or the auth token model — all inherited unchanged
  from `docs/superpowers/specs/2026-08-04-frontend-design.md`.
- A font swap — Geist stays.

## 1. Visual system

Chosen via the visual companion: four style directions (energetic athletic, clean minimal
fitness-tech, dark-mode-first, warm human coach) were shown as mockups; clean minimal fitness-tech
was selected, then refined across three light-blue accent shades (sky/cornflower/powder) down to
cornflower blue.

**Palette** (replaces the existing zero-chroma shadcn tokens in `globals.css`, same variable names):

| Token | Value | Used for |
|---|---|---|
| `--background` | `#fafaf9` | Page background |
| `--card` | `#ffffff` | Card surfaces |
| `--border` | `#e8e6e1` | Card/input hairline borders |
| `--foreground` | `#1a1a1a` | Primary text |
| `--muted-foreground` | `#8a8a85` | Secondary text, eyebrow labels |
| `--primary` | `#4f7cf6` (cornflower blue) | Buttons, links, score highlights |
| `--primary-foreground` | `#ffffff` | Text/icons on `--primary` |
| `--destructive` | *(unchanged)* | Errors, delete action — existing red already reads fine against the new background, not part of this pass |

**Mechanism:** these are substituted `oklch()` values behind the *existing* CSS custom properties in
`frontend/src/app/globals.css`. Every shadcn component (`Button`, `Card`, `Input`, `Label`, `Alert`)
already consumes these tokens exclusively (confirmed by reading `components/ui/button.tsx` — variants
are built entirely from `bg-primary`, `bg-muted`, `text-destructive`, etc., no hardcoded colors) — so
this is a token-value edit, not a component-code change.

**Typography:** Geist (already loaded) stays. Add a consistent type scale, replacing today's ad hoc
per-page classes:
- **Eyebrow label** — small, uppercase, letter-spaced, `--muted-foreground` (e.g. "Latest score",
  "Status").
- **Page title** — `text-2xl font-semibold`, standardized across all four pages (today only the home
  page uses this consistently).
- **Display number** — `text-4xl font-bold`, `--primary`-colored — for the overall/rep score.
- **Body** — existing Tailwind defaults, unchanged.

**Radius:** `--radius` moves from `0.625rem` to `0.75rem` (softer corners, matches the approved
mockup). Every component's radius (`--radius-sm` through `--radius-4xl` in `globals.css`) is already
derived from this one variable via `calc()`, so this is a one-line change.

## 2. Site chrome

No shared header exists today — the home page has an ad-hoc "Log out" button next to its own
`<h1>`, and the attempt-detail page has no header or logout access at all.

**New component: `AppShell`** (`frontend/src/components/app-shell.tsx`) — a slim top bar: wordmark
"AI Fitness Trainer" on the left, a plain-text "Log out" button on the right (reusing `useAuth`'s
`logout`, same call the home page makes today). Wraps the two authenticated pages (`/`,
`/attempts/[id]`) — login/register stay chrome-less (no session yet to show a logout control for).

**Kept separate from `ProtectedRoute`** rather than folded into it, so each component keeps one job:
`ProtectedRoute` gates access, `AppShell` renders chrome. Usage becomes
`<ProtectedRoute><AppShell>{content}</AppShell></ProtectedRoute>` on both pages. This is a plain
component wrapper, not a Next.js route-group layout — no file-structure/routing change.

## 3. Page-by-page polish

- **Login / register:** no structural change. Inherit the new palette/type scale automatically via
  the token swap (they already use `Card`/`Input`/`Label`/`Button`/`Alert`).
- **Home:** `AppShell` replaces the current inline `<h1>Your attempts</h1>` + logout-button row. The
  upload form keeps the native `<input type="file">` (no new dependency) but gains Tailwind `file:`
  pseudo-element styling so it reads as a real control instead of the browser default — same element,
  same `handleFileChange`, no behavior change.
- **History list (`AttemptHistoryList`):** today's row is a bare 3-span flex (`exercise_type | status
  | score`). Restyle only: status becomes a small colored pill (`--muted` for
  queued/processing, `--primary` for completed, `--destructive` for failed), score becomes the
  visually prominent element, subtle hover state on the row. Same three fields already returned by
  `GET /v1/attempts` — nothing new is fetched or displayed.
- **Attempt result (`AttemptResult`):** the score card adopts the eyebrow-label + display-number
  treatment from §1. Per-rep rows and error badges (`formErrorMessage`) keep their exact current
  logic, restyled to the new tokens only.

## 4. Constraints

**No behavior changes.** Every interaction, API call, error path, loading/empty state, and piece of
component state stays exactly as implemented in frontend-v1. This pass is markup/class-level styling
plus one new purely-presentational component (`AppShell`); it does not touch `apiFetch`,
`auth-context.tsx`, any hook, or any `lib/*` module. This is a hard constraint for whoever implements
each task, not just a description of current intent.

## 5. Testing

Existing Vitest/RTL component tests and the Playwright e2e test should continue passing largely
unmodified, since queries are expected to target text/roles rather than CSS classes. The one
structural change is `AppShell`'s wrapper markup around the home page's "Log out" button (previously
a bare `Button` in the page body) — each task touching a page should confirm no existing test was
asserting DOM structure that shifts because of the new wrapper, and fix forward if so rather than
weakening the assertion.

## 6. Explicitly out of scope

- Dark mode (existing unused `.dark` tokens revisited in a later pass).
- Any redesign of page structure, navigation/IA, or user flows.
- A font change away from Geist.
- New data fields in the history list or result view beyond what the backend already returns.
