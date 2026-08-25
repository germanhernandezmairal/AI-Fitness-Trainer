# Frontend Redesign — Confident Data-Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retheme the frontend from the 2026-08-12 light-only cornflower-blue palette to a dark+light "Confident Data-Product" system (near-black navy/indigo, WCAG-AA-verified) with a user-facing toggle, switch typography from Geist to Inter, and fix the three places the brand color is used as text so they pass AA — with zero changes to behavior, routing, IA, or data flow.

**Architecture:** Every shadcn component already reads its colors exclusively from CSS custom properties in `frontend/src/app/globals.css` (confirmed unchanged since the 2026-08-12 pass — no component hardcodes a color). Retheming both palettes and adding a `--primary-text` token is therefore a token-value edit. The theme toggle is `next-themes` (new dependency) wired once in `Providers`, reading/writing the existing `.dark` class selector `globals.css` already defines. Typography is a `next/font/google` swap in the root layout. No new pages, no new API calls, no new component state beyond the toggle's own theme value (owned entirely by `next-themes`).

**Tech Stack:** Next.js 16 (App Router), Tailwind CSS v4, shadcn/ui (Base UI primitives), `next-themes` (new), `lucide-react` (already a dependency, used here for the toggle icon), Vitest + React Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-25-frontend-redesign-design.md`

## Global Constraints

- **No behavior changes.** Every interaction, API call, error path, loading/empty state, and piece of component state stays exactly as implemented in frontend-v1 and the 2026-08-12 pass. This plan touches `globals.css`, `app/layout.tsx`, `app/providers.tsx`, `components/app-shell.tsx`, and the three files that use `text-primary` as text — nothing else, and none of `apiFetch`, `auth-context.tsx`, any hook, or any `lib/*` module.
- **Re-skin only.** No new views, no navigation/IA change, no component restructuring beyond what the token/font/toggle swap requires.
- **`--destructive` (error red) is unchanged** — out of scope for this pass.
- **`--font-mono` (Geist Mono) is unchanged** — stays loaded, used nowhere meaningful today, not part of this pass.
- **Motion stays minimal.** No entrance/list/score-reveal animations are added by this plan.
- **Exact palette** (replaces the existing `globals.css` tokens, same variable names, plus one new token):
  - Light `:root`: `--background: #f7f8fb`, `--card`/`--popover`: `#ffffff`, `--card-foreground`/`--popover-foreground`/`--foreground`: `#12162a`, `--muted-foreground: #5b6178`, `--primary: #4a5ae0`, `--primary-foreground: #ffffff`, `--primary-text: #4a5ae0`, `--secondary`/`--muted`/`--accent`: `#eef0f7`, `--secondary-foreground`/`--accent-foreground`: `#12162a`, `--border`/`--input`: `#7c85ba`, `--ring: var(--primary-text)`.
  - Dark `.dark`: `--background: #0b0f1a`, `--card`/`--popover`: `#141a2b`, `--card-foreground`/`--popover-foreground`/`--foreground`: `#f4f6fb`, `--muted-foreground: #8890ab`, `--primary: #5261e8`, `--primary-foreground: #ffffff`, `--primary-text: #6d78f6`, `--secondary`/`--muted`/`--accent`: `#1b2338`, `--secondary-foreground`/`--accent-foreground`: `#f4f6fb`, `--border`/`--input`: `#556086`, `--ring: var(--primary-text)`.
  - `--chart-*` and `--sidebar-*` tokens: **unchanged** — nothing in the app currently renders a chart or sidebar.
  - `--radius`: **unchanged** (`0.75rem`, set in the 2026-08-12 pass).
- **`--primary-text` rule:** the brand indigo has two jobs — solid button backgrounds (`bg-primary text-primary-foreground`, unchanged) and bare text/links/icons directly on the page or card background. The latter must use the new `text-primary-text` utility, never `text-primary` — `text-primary` on a background fails AA in the dark theme (verified in the spec). Every existing bare-text use of `text-primary` in the codebase is converted in Task 5.
- **Font:** Inter replaces Geist as `--font-sans`. `next/font/google`'s `Inter` import, same pattern already used for `Geist`/`Geist_Mono`.

---

### Task 1: Retheme design tokens (light + dark, plus the new `--primary-text` token)

**Files:**
- Modify: `frontend/src/app/globals.css:7-118` (the `@theme inline` block, `:root`, and `.dark`)

**Interfaces:**
- Consumes: nothing (CSS-only change).
- Produces: the palette values from Global Constraints, available to every component via the existing `var(--token-name)` mechanism, plus a new `text-primary-text`/`bg-primary-text` Tailwind utility (via `--color-primary-text` in `@theme inline`) that Task 5 consumes.

This is a pure CSS-value edit with no new logic to unit-test, so instead of a TDD cycle this task is verified by confirming the existing suite still passes and the app still builds with the new values — same approach as the 2026-08-12 retheme task.

- [ ] **Step 1: Run the full test suite to record the passing baseline**

Run: `cd frontend && npm test`
Expected: all existing tests PASS (this is the baseline — the retheme must not break it).

- [ ] **Step 2: Replace the theme-inline, `:root`, and `.dark` blocks**

Replace lines 7-118 of `frontend/src/app/globals.css` (from `@theme inline {` through the closing `}` of the `.dark` block) with:

```css
@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
  --font-heading: var(--font-sans);
  --color-sidebar-ring: var(--sidebar-ring);
  --color-sidebar-border: var(--sidebar-border);
  --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
  --color-sidebar-accent: var(--sidebar-accent);
  --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
  --color-sidebar-primary: var(--sidebar-primary);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar: var(--sidebar);
  --color-chart-5: var(--chart-5);
  --color-chart-4: var(--chart-4);
  --color-chart-3: var(--chart-3);
  --color-chart-2: var(--chart-2);
  --color-chart-1: var(--chart-1);
  --color-ring: var(--ring);
  --color-input: var(--input);
  --color-border: var(--border);
  --color-destructive: var(--destructive);
  --color-accent-foreground: var(--accent-foreground);
  --color-accent: var(--accent);
  --color-muted-foreground: var(--muted-foreground);
  --color-muted: var(--muted);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-secondary: var(--secondary);
  --color-primary-foreground: var(--primary-foreground);
  --color-primary-text: var(--primary-text);
  --color-primary: var(--primary);
  --color-popover-foreground: var(--popover-foreground);
  --color-popover: var(--popover);
  --color-card-foreground: var(--card-foreground);
  --color-card: var(--card);
  --radius-sm: calc(var(--radius) * 0.6);
  --radius-md: calc(var(--radius) * 0.8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --radius-2xl: calc(var(--radius) * 1.8);
  --radius-3xl: calc(var(--radius) * 2.2);
  --radius-4xl: calc(var(--radius) * 2.6);
}

:root {
  --background: #f7f8fb;
  --foreground: #12162a;
  --card: #ffffff;
  --card-foreground: #12162a;
  --popover: #ffffff;
  --popover-foreground: #12162a;
  --primary: #4a5ae0;
  --primary-foreground: #ffffff;
  --primary-text: #4a5ae0;
  --secondary: #eef0f7;
  --secondary-foreground: #12162a;
  --muted: #eef0f7;
  --muted-foreground: #5b6178;
  --accent: #eef0f7;
  --accent-foreground: #12162a;
  --destructive: oklch(0.577 0.245 27.325);
  --border: #7c85ba;
  --input: #7c85ba;
  --ring: var(--primary-text);
  --chart-1: oklch(0.87 0 0);
  --chart-2: oklch(0.556 0 0);
  --chart-3: oklch(0.439 0 0);
  --chart-4: oklch(0.371 0 0);
  --chart-5: oklch(0.269 0 0);
  --radius: 0.75rem;
  --sidebar: oklch(0.985 0 0);
  --sidebar-foreground: oklch(0.145 0 0);
  --sidebar-primary: oklch(0.205 0 0);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.97 0 0);
  --sidebar-accent-foreground: oklch(0.205 0 0);
  --sidebar-border: oklch(0.922 0 0);
  --sidebar-ring: oklch(0.708 0 0);
}

.dark {
  --background: #0b0f1a;
  --foreground: #f4f6fb;
  --card: #141a2b;
  --card-foreground: #f4f6fb;
  --popover: #141a2b;
  --popover-foreground: #f4f6fb;
  --primary: #5261e8;
  --primary-foreground: #ffffff;
  --primary-text: #6d78f6;
  --secondary: #1b2338;
  --secondary-foreground: #f4f6fb;
  --muted: #1b2338;
  --muted-foreground: #8890ab;
  --accent: #1b2338;
  --accent-foreground: #f4f6fb;
  --destructive: oklch(0.704 0.191 22.216);
  --border: #556086;
  --input: #556086;
  --ring: var(--primary-text);
  --chart-1: oklch(0.87 0 0);
  --chart-2: oklch(0.556 0 0);
  --chart-3: oklch(0.439 0 0);
  --chart-4: oklch(0.371 0 0);
  --chart-5: oklch(0.269 0 0);
  --sidebar: oklch(0.205 0 0);
  --sidebar-foreground: oklch(0.985 0 0);
  --sidebar-primary: oklch(0.488 0.243 264.376);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.269 0 0);
  --sidebar-accent-foreground: oklch(0.985 0 0);
  --sidebar-border: oklch(1 0 0 / 10%);
  --sidebar-ring: oklch(0.556 0 0);
}
```

Note: `--font-sans` still points at `--font-geist-sans` here — Task 3 changes that one line when it swaps the font. `--sidebar*`/`--chart-*` values are byte-for-byte unchanged from before this edit, only reformatted by being part of the same replaced block.

- [ ] **Step 3: Run the full test suite again**

Run: `cd frontend && npm test`
Expected: same PASS result as Step 1 — a CSS token change should not affect any test outcome.

- [ ] **Step 4: Confirm the app still builds**

Run: `cd frontend && npm run build`
Expected: build succeeds with no Tailwind/CSS errors.

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/app/globals.css
git commit -m "style(frontend): retheme to dark+light Confident Data-Product palette"
```

---

### Task 2: Add the `next-themes` toggle provider

**Files:**
- Modify: `frontend/package.json` (via `npm install`)
- Modify: `frontend/src/app/providers.tsx`
- Modify: `frontend/src/app/layout.tsx`

**Interfaces:**
- Consumes: nothing new from earlier tasks.
- Produces: a mounted `ThemeProvider` (from `next-themes`) wrapping the app, using `attribute="class"` so it toggles the same `.dark` class selector `globals.css` already defines. Task 4's `ThemeToggle` consumes `useTheme()` from `"next-themes"`, which only works because this task's `ThemeProvider` is mounted above it in the tree.

- [ ] **Step 1: Install the dependency**

Run: `cd frontend && npm install next-themes`
Expected: `next-themes` appears under `"dependencies"` in `frontend/package.json`, and `frontend/package-lock.json` updates.

- [ ] **Step 2: Wire `ThemeProvider` into `Providers`**

In `frontend/src/app/providers.tsx`, add the import alongside the existing ones:

```tsx
import { ThemeProvider } from "next-themes";
```

Then replace the `return` statement of the `Providers` component:

```tsx
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
```

with:

```tsx
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
```

`disableTransitionOnChange` keeps a theme switch instant (no cross-fade flash), matching the minimal-motion constraint. `defaultTheme="system"`/`enableSystem` mean a first-time visitor sees their OS preference, and `next-themes` persists any explicit choice to `localStorage` on its own — no app code writes theme state directly.

- [ ] **Step 3: Suppress the expected hydration warning on `<html>`**

`next-themes` sets the `.dark` class on the real DOM before React hydrates (to avoid a flash of the wrong theme), which makes the server-rendered and first-hydrated `<html>` markup legitimately differ — Next.js/React would otherwise log a hydration-mismatch warning for this one, expected case. In `frontend/src/app/layout.tsx`, change:

```tsx
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
```

to:

```tsx
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
```

(Task 3 changes `geistSans` to `inter` on this same line — this step only adds the `suppressHydrationWarning` attribute.)

- [ ] **Step 4: Run the full test suite**

Run: `cd frontend && npm test`
Expected: all tests PASS unchanged — no existing test renders the real `Providers` tree (each page/component test mocks `@/lib/auth-context` and any hooks it needs directly), so `ThemeProvider` is never exercised by the current suite.

- [ ] **Step 5: Confirm the app still builds**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add package.json package-lock.json src/app/providers.tsx src/app/layout.tsx
git commit -m "feat(frontend): add next-themes theme provider"
```

---

### Task 3: Switch typography from Geist to Inter

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/app/globals.css:10` (the `--font-sans` line inside `@theme inline`)

**Interfaces:**
- Consumes: nothing new from earlier tasks.
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Run the full test suite to record the passing baseline**

Run: `cd frontend && npm test`
Expected: all tests PASS (baseline).

- [ ] **Step 2: Swap the font import and loader**

In `frontend/src/app/layout.tsx`, change:

```tsx
import { Geist, Geist_Mono } from "next/font/google";
```

to:

```tsx
import { Inter, Geist_Mono } from "next/font/google";
```

and change:

```tsx
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});
```

to:

```tsx
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});
```

`Geist_Mono`'s own `const geistMono = Geist_Mono({ ... })` is unchanged — `--font-mono` stays Geist Mono per Global Constraints.

- [ ] **Step 3: Update the `<html>` className to use the new font variable**

Change:

```tsx
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
```

to:

```tsx
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
```

- [ ] **Step 4: Point `--font-sans` at the new variable**

In `frontend/src/app/globals.css`, inside the `@theme inline` block, change:

```css
  --font-sans: var(--font-geist-sans);
```

to:

```css
  --font-sans: var(--font-inter);
```

This also fixes, as a side effect, the pre-existing self-reference bug the 2026-08-12 pass found and worked around for Geist (`--font-sans: var(--font-sans)` in frontend-v1) — Inter becomes the actual resolved target instead of Geist.

- [ ] **Step 5: Run the full test suite again**

Run: `cd frontend && npm test`
Expected: same PASS result as Step 1 — no test asserts on font family.

- [ ] **Step 6: Confirm the app still builds**

Run: `cd frontend && npm run build`
Expected: build succeeds (same `next/font/google` mechanism already proven to work for Geist in this repo).

- [ ] **Step 7: Commit**

```bash
cd frontend
git add src/app/layout.tsx src/app/globals.css
git commit -m "style(frontend): switch typography from Geist to Inter"
```

---

### Task 4: Add the theme toggle to `AppShell`

**Files:**
- Modify: `frontend/src/components/app-shell.tsx`
- Modify: `frontend/tests/unit/components/app-shell.test.tsx`

**Interfaces:**
- Consumes: `useTheme()` from `"next-themes"` (Task 2's `ThemeProvider`, mounted above `AppShell` in the real app — mocked directly in this task's tests, same pattern as the existing `useAuth` mock in this file), `Moon`/`Sun` from `"lucide-react"`.
- Produces: nothing new consumed by later tasks.

The spec's testing note (§7) frames toggle coverage in terms of the real `.dark` class/`localStorage` persistence `next-themes` manages. This task tests the app's own logic instead — that clicking the toggle calls `setTheme` with the correct opposite value — by mocking `next-themes` at the module boundary, the same way every other test in this file already mocks `@/lib/auth-context`. The actual class-toggling and persistence behavior lives entirely inside `next-themes` itself (a maintained third-party library, not app code), so re-testing it here would just be testing the dependency; this task's job is to prove `AppShell` calls it correctly.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `frontend/tests/unit/components/app-shell.test.tsx` with:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const mockLogout = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ logout: mockLogout }) }));

const mockSetTheme = vi.fn();
let mockResolvedTheme = "light";
vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: mockResolvedTheme, setTheme: mockSetTheme }),
}));

import { AppShell } from "@/components/app-shell";

describe("AppShell", () => {
  afterEach(() => {
    cleanup();
    mockLogout.mockReset();
    mockSetTheme.mockReset();
    mockResolvedTheme = "light";
  });

  it("renders the wordmark and its children", () => {
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );

    expect(screen.getByText("AI Fitness Trainer")).toBeInTheDocument();
    expect(screen.getByText("page content")).toBeInTheDocument();
  });

  it("links the wordmark back to /", () => {
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: "AI Fitness Trainer" })).toHaveAttribute(
      "href",
      "/",
    );
  });

  it("calls logout when the Log out button is clicked", async () => {
    mockLogout.mockResolvedValueOnce(undefined);
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /log out/i }));

    expect(mockLogout).toHaveBeenCalled();
  });

  it("renders a theme toggle button", () => {
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );

    expect(screen.getByRole("button", { name: /toggle theme/i })).toBeInTheDocument();
  });

  it("switches to dark when toggled while the resolved theme is light", async () => {
    mockResolvedTheme = "light";
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /toggle theme/i }));

    expect(mockSetTheme).toHaveBeenCalledWith("dark");
  });

  it("switches to light when toggled while the resolved theme is dark", async () => {
    mockResolvedTheme = "dark";
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /toggle theme/i }));

    expect(mockSetTheme).toHaveBeenCalledWith("light");
  });
});
```

- [ ] **Step 2: Run the test to verify the new tests fail**

Run: `cd frontend && npx vitest run tests/unit/components/app-shell.test.tsx`
Expected: the 3 pre-existing tests PASS, the 3 new toggle tests FAIL (no button matching `/toggle theme/i` exists yet).

- [ ] **Step 3: Add the toggle to the implementation**

Replace the full contents of `frontend/src/components/app-shell.tsx` with:

```tsx
"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Until mounted, resolvedTheme reflects the server render (no system-preference
  // read yet) — render a disabled placeholder rather than guess and risk a
  // hydration mismatch between server and client icon.
  if (!mounted) {
    return <Button variant="ghost" size="icon-sm" aria-label="Toggle theme" disabled />;
  }

  const isDark = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="Toggle theme"
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth();

  return (
    <div className="min-h-full">
      <header className="border-b border-border bg-card px-6 py-3">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <Link href="/" className="text-base font-semibold">
            AI Fitness Trainer
          </Link>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={() => logout()}>
              Log out
            </Button>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/components/app-shell.test.tsx`
Expected: PASS (6 tests).

- [ ] **Step 5: Run the full unit suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: all tests PASS — `home-page.test.tsx` and `attempt-detail-page.test.tsx` both render `AppShell` indirectly but mock `@/lib/auth-context` only, not `next-themes`; confirm they still pass with the real (unmocked) `next-themes` module loaded (its bare `useTheme()` call outside any `ThemeProvider` returns safe no-op defaults — it does not throw, and neither of those test files asserts anything about the toggle).

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/components/app-shell.tsx tests/unit/components/app-shell.test.tsx
git commit -m "feat(frontend): add theme toggle to AppShell"
```

---

### Task 5: Convert brand-color text usage to `text-primary-text`, final verification

**Files:**
- Modify: `frontend/src/components/attempt-history-list.tsx:16`
- Modify: `frontend/src/components/attempt-result.tsx:19,33`
- Modify: `frontend/src/components/ui/button.tsx:20`
- Modify: `frontend/tests/unit/components/attempt-history-list.test.tsx`
- Modify: `frontend/tests/unit/components/attempt-result.test.tsx`

**Interfaces:**
- Consumes: the `text-primary-text` Tailwind utility from Task 1's `--color-primary-text` token.
- Produces: nothing new consumed by later tasks — this is the plan's last task.

Three real call sites use `text-primary` as bare text color today (found via `grep -rn "text-primary\b"` across `frontend/src`): the completed-status pill, the overall score, and the per-rep score. A fourth, `button.tsx`'s `link` variant, is a generic shadcn primitive with the same bare-text pattern but currently has zero call sites in the app (`grep -rn 'variant="link"'` across `frontend/src` finds none) — fixed anyway for consistency and so it's correct the first time it's ever used, but has no test coverage to add since nothing renders it.

- [ ] **Step 1: Write the failing tests**

In `frontend/tests/unit/components/attempt-history-list.test.tsx`, inside the `"gives each status a distinct pill style"` test, change:

```tsx
    expect(completedPill.className).toContain("text-primary");
```

to:

```tsx
    expect(completedPill.className.split(" ")).toContain("text-primary-text");
    expect(completedPill.className.split(" ")).not.toContain("text-primary");
```

(`toContain` alone would still pass against the unfixed code, since the string `"text-primary"` is a substring of `"text-primary-text"` — splitting on spaces and matching the exact class token is what actually distinguishes the two.)

In `frontend/tests/unit/components/attempt-result.test.tsx`, inside the `"gives per-rep scores the same eyebrow/display type-scale as the overall score"` test, change:

```tsx
    expect(repScore.className).toContain("text-primary");
```

to:

```tsx
    expect(repScore.className.split(" ")).toContain("text-primary-text");
    expect(repScore.className.split(" ")).not.toContain("text-primary");
```

- [ ] **Step 2: Run both test files to verify the changed assertions fail**

Run: `cd frontend && npx vitest run tests/unit/components/attempt-history-list.test.tsx tests/unit/components/attempt-result.test.tsx`
Expected: both files FAIL on the assertions just changed (current code still emits bare `text-primary` on both elements).

- [ ] **Step 3: Convert the three real call sites**

In `frontend/src/components/attempt-history-list.tsx`, change:

```tsx
  completed: "bg-primary/10 text-primary",
```

to:

```tsx
  completed: "bg-primary/10 text-primary-text",
```

In `frontend/src/components/attempt-result.tsx`, change:

```tsx
        <p className="text-4xl font-bold text-primary">
```

to:

```tsx
        <p className="text-4xl font-bold text-primary-text">
```

and change:

```tsx
              <span className="text-xl font-bold text-primary">
```

to:

```tsx
              <span className="text-xl font-bold text-primary-text">
```

- [ ] **Step 4: Convert the unused fourth call site**

In `frontend/src/components/ui/button.tsx`, change:

```tsx
        link: "text-primary underline-offset-4 hover:underline",
```

to:

```tsx
        link: "text-primary-text underline-offset-4 hover:underline",
```

- [ ] **Step 5: Run both test files to verify they pass**

Run: `cd frontend && npx vitest run tests/unit/components/attempt-history-list.test.tsx tests/unit/components/attempt-result.test.tsx`
Expected: PASS (5 tests in `attempt-history-list.test.tsx`, 7 in `attempt-result.test.tsx`).

- [ ] **Step 6: Run the full unit suite**

Run: `cd frontend && npm test`
Expected: all tests PASS across the whole suite — the final confirmation that all 5 tasks compose cleanly.

- [ ] **Step 7: Confirm the app still builds**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 8: Commit**

```bash
cd frontend
git add src/components/attempt-history-list.tsx src/components/attempt-result.tsx src/components/ui/button.tsx tests/unit/components/attempt-history-list.test.tsx tests/unit/components/attempt-result.test.tsx
git commit -m "fix(frontend): use text-primary-text for brand-color text, not text-primary"
```
