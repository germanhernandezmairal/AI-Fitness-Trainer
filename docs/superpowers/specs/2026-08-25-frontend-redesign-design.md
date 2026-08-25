# Design: Frontend Redesign — Confident Data-Product

**Date:** 2026-08-25
**Author:** Compiled with Claude (via `superpowers:brainstorming`, using the visual companion for
typography selection; brainstorm started 2026-08-24, finished 2026-08-25)
**Status:** APPROVED (2026-08-25)
**Related:** `docs/superpowers/specs/2026-08-04-frontend-design.md` (frontend-v1 design — pages,
components, auth, error-handling described there are unchanged), `docs/superpowers/specs/
2026-08-12-frontend-design-polish-design.md` (first visual pass — cornflower-blue light-only
palette, `AppShell`, type scale; this design replaces its palette but keeps its structural
decisions), `docs/superpowers/specs/2026-08-13-frontend-follow-up-polish-design.md` (deferred
findings from that pass, since resolved — confirmed current `AppShell`/attempt-detail code already
reflects the fixes, e.g. the wordmark is already a `Link`, `AppShell` already wraps the
attempt-detail page once around every status branch rather than three times).

---

## 0. Context and goal

Frontend-v1 shipped functional; the 2026-08-12 polish pass gave it a real (light-only) visual
system — cornflower-blue accent, a type scale, `AppShell` header. Per the work split agreed with
Alejandro (2026-08-11): Alejandro owns `cv-service` accuracy, the user owns frontend design. This
is the next design iteration on that piece — explicitly a **bigger leap this time**, not another
polish pass (both 2026-08-12 and 2026-08-13 were scoped "polish, not redesign"; the user asked for
more this round).

**Scope decision (resolved first, before any visual direction):** a **re-skin**, not an
IA/structural redesign. The existing 4 screens (login/register, home+upload, history, attempt
detail) and their flows stay; only their visual system changes. No new views (e.g. no progress/
trend view), no navigation change, no component restructuring beyond what a token/font/toggle swap
requires.

**Explicitly out of scope:**
- Any change to routing, page structure, data flow, or the auth token model — all inherited
  unchanged from `docs/superpowers/specs/2026-08-04-frontend-design.md`.
- New data fields in the history list or result view beyond what the backend already returns.
- `--destructive` (error red) — unchanged, out of scope for this pass.
- Entrance/list animations, animated score reveals, or any "expressive" motion (see §3).

## 1. Visual direction

Chosen via the visual companion (2026-08-24): four style directions (Confident Data-Product,
Athletic Energy, Calm Coach, Refined Minimal Dark) were shown as header+score-card mockups.
**Confident Data-Product** was selected — a near-black navy/indigo system in the Linear/Vercel
register, replacing 2026-08-12's light cornflower-blue palette.

**Decided the same session:** both light and dark themes, with a toggle (not dark-only) —
2026-08-12 deliberately left dark mode for "a later pass"; this is that pass.

## 2. Color tokens

Both palettes were built and verified against WCAG 2.1 AA using the relative-luminance contrast
formula (not eyeballed) — RNF-7 in the memoria (`memoria/04-requisitos.md`) commits to AA
conformance as an *objetivo*, unaudited so far; this pass is the point to actually close that gap
for the app's chrome and text, not just claim it.

These substitute the existing `oklch()`/hex values behind the same CSS custom properties in
`frontend/src/app/globals.css` (`:root` for light, `.dark` for dark — the `.dark` class selector
already exists, unused, from shadcn's scaffold). Every shadcn component already consumes these
tokens exclusively (confirmed in `components/ui/button.tsx` et al. during the 2026-08-12 pass, and
no component-level color hardcoding has been added since) — so this is a token-value edit, not a
component-code change, in every file except `AppShell` (§4).

| Token | Light | Dark | Contrast verified |
|---|---|---|---|
| `--background` | `#f7f8fb` | `#0b0f1a` | — |
| `--card` / `--popover` | `#ffffff` | `#141a2b` | — |
| `--card-foreground` / `--popover-foreground` / `--foreground` | `#12162a` | `#f4f6fb` | 16.8-17.9:1 (AA normal text) |
| `--muted-foreground` | `#5b6178` | `#8890ab` | 5.8-6.1:1 vs bg/card (AA normal text) |
| `--primary` | `#4a5ae0` | `#5261e8` | white-on-it (button label): 5.48:1 / 4.96:1 (AA normal text) |
| `--primary-foreground` | `#ffffff` | `#ffffff` | — |
| `--primary-text` *(new token, see below)* | `#4a5ae0` | `#6d78f6` | vs bg: 5.16:1 both themes (AA normal text) |
| `--border` / `--input` | `#7c85ba` | `#556086` | vs card/bg: 3.10-3.55:1 (AA non-text/UI-component) |
| `--ring` (focus) | `--primary-text` | `--primary-text` | inherits `--primary-text` |
| `--secondary` / `--muted` / `--accent` (shadcn's neutral hover/highlight surfaces — unrelated to the brand indigo) | a subtle indigo-tinted neutral, e.g. `#eef0f7` / `#1b2338` | same | not independently load-bearing for text; foreground pairing reuses `--foreground` |
| `--destructive` | *unchanged* | *unchanged* | out of scope |

**Why `--primary-text` exists as a token separate from `--primary`:** the brand indigo does two
different jobs — solid button backgrounds (`bg-primary text-primary-foreground`) and bare text/
links/icons directly on the page or card background. No single indigo shade in this hue clears
4.5:1 AA for *both* jobs at once on the dark background (`#5b6bf5`, the value first proposed
2026-08-24, came in at 4.43:1 as text and 4.32:1 as a button label under white text — both fail by
a hair). Splitting into two purpose-built shades is the standard fix; every other shadcn component
already expects a single `--primary`/`--primary-foreground` pair for solid surfaces, so
`--primary-text` is additive, not a rename — it's a new utility (e.g. a `text-primary-text`
Tailwind class via `@theme inline`) for the specific case of the brand color appearing as text: the
history list's completed-status pill text, the attempt-detail wordmark/link, focus rings, and
anywhere else `text-primary` would currently be reached for.

**Border trade-off decision:** the card background is barely distinguishable from the page
background on its own (`#141a2b` vs `#0b0f1a` — 1.1:1; `#ffffff` vs `#f7f8fb` — 1.06:1), so the
border is load-bearing for perceiving a card's edges, not decorative — it needs to clear WCAG's
3:1 non-text-contrast bar for UI components, not just be a faint hairline. Reference sites (Linear,
Vercel) typically use an even fainter border that does *not* clear 3:1 on its own. **Decided:**
go with the compliant, slightly more visible border (`#556086` dark / `#7c85ba` light) over the
faint reference-site look, given RNF-7's AA commitment.

## 3. Typography and motion

**Typography:** shown via the visual companion as three score-card specimens (keep Geist / switch
to Inter / Space Grotesk+Inter split) — **Inter, one typeface everywhere** (wordmark, display
numbers, body) was selected over keeping Geist or splitting families. Replaces `--font-sans` (and
therefore also fixes, as a side effect, the pre-existing `--font-sans: var(--font-sans)`
self-reference bug from frontend-v1 that the 2026-08-12 pass already found and worked around for
Geist — Inter becomes the actual target instead). `--font-mono` (Geist Mono, used nowhere
meaningful today) is not part of this pass; leave as-is unless implementation finds an actual use.

**Motion:** minimal, decided directly (not via the visual companion — a preference question, not a
visual one). Instant state changes; at most a quick opacity/hover transition on interactive
elements. No entrance animations, no staggered list reveals, no animated score reveal on the result
screen.

## 4. Theme toggle

New dependency: **`next-themes`** — the standard pairing for shadcn/ui projects (handles
system-preference default, `localStorage` persistence, and avoiding a flash-of-wrong-theme on load
without hand-rolling a blocking inline script). Not currently a dependency; add via `npm install`.

Wraps the app in root layout (`app/layout.tsx`) via `next-themes`'s `ThemeProvider`, alongside the
existing `AuthProvider`/`QueryClientProvider`. Toggle control (sun/moon icon button, `next-themes`'s
`useTheme` hook) lives in `AppShell`'s header (`frontend/src/components/app-shell.tsx`), to the left
of the existing "Log out" button — the only new UI element this pass adds. Default: system
preference, per `next-themes`'s standard behavior; user's explicit choice persists across sessions
via `localStorage`.

`AppShell` itself needs no other change — it already wraps both authenticated pages
(`app/page.tsx`, `app/attempts/[id]/page.tsx`) consistently, once each, around every status branch
(confirmed current code, not assumed from the 2026-08-13 plan — that deferred finding was already
fixed).

## 5. Page-by-page

All four screens inherit the new palette/type scale/toggle automatically via the token swap and the
`AppShell` toggle addition — none need structural changes:

- **Login / register:** no structural change. Already use `Card`/`Input`/`Label`/`Button`/`Alert`,
  all token-driven.
- **Home:** `AppShell` header gains the toggle. Upload form's `file:` pseudo-element styling
  (added 2026-08-12) is token-driven already, no direct edit needed.
- **History list (`AttemptHistoryList`):** status pills (`STATUS_PILL_CLASSES`, added 2026-08-12)
  are token-driven — verify each pill's text still passes AA against the new tokens; the
  `--primary`-colored "completed" pill in particular should use `--primary-text` for its label
  color, not `--primary`, per §2.
- **Attempt result (`AttemptResult`):** score card's eyebrow-label/display-number treatment is
  token-driven, no direct edit needed beyond the same `--primary` → `--primary-text` check on any
  text-colored (not background-colored) use of the brand color.

## 6. Constraints

**No behavior changes.** Every interaction, API call, error path, loading/empty state, and piece of
component state stays exactly as implemented in frontend-v1 and the 2026-08-12 pass. This pass is
token values, font, one new `AppShell` toggle control, and the `next-themes` provider wiring; it
does not touch `apiFetch`, `auth-context.tsx`, any hook, or any `lib/*` module (`next-themes`'s
`ThemeProvider` is purely presentational — it does not read or write auth state).

## 7. Testing

Existing Vitest/RTL component tests and the Playwright e2e test should continue passing largely
unmodified, since queries are expected to target text/roles rather than CSS classes or literal
color values. The one new piece of real behavior is the toggle itself — needs its own test coverage
(toggle renders, click switches the `.dark` class / `data-theme` attribute `next-themes` manages,
choice persists across a re-render). Any place a test asserts on a specific class name derived from
`--primary` (e.g. `text-primary`) that now needs to read `text-primary-text` per §2 should be caught
and fixed forward, not weakened.

## 8. Explicitly out of scope

- Any redesign of page structure, navigation/IA, or user flows.
- New views (progress/trend screens, etc.).
- New data fields beyond what the backend already returns.
- `--destructive` (error red) restyling.
- Entrance/list/score-reveal animations — motion stays minimal (§3).
- `--font-mono` / Geist Mono changes.
