# Frontend Follow-Up Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 5 deferred Minor findings from the 2026-08-12 frontend-design-polish review —
per-rep score type-scale, `AttemptDetailContent`'s inconsistent wrap/width, the `AppShell` wordmark
link, and `STATUS_PILL_CLASSES`'s missing fallback.

**Architecture:** 4 independent tasks, each touching one existing component + its existing test
file (no new files). TDD throughout: failing test first, minimal fix, verify, commit.

**Tech Stack:** Next.js 16 App Router, Vitest + `@testing-library/react`, Tailwind classes (no CSS
modules/`@apply` in this codebase — type-scale is applied via repeated utility-class combos, not a
shared token component).

## Global Constraints

- All work happens in `frontend/` in the main Cursor clone
  (`/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer`).
- No new components, no routing/data-flow changes, no dark mode — per
  `docs/superpowers/specs/2026-08-13-frontend-follow-up-polish-design.md` §0.
- Eyebrow label class (reused verbatim from the overall score): `text-[11px] font-medium uppercase
  tracking-wide text-muted-foreground`.
- Display number treatment (reused, sized down from `text-4xl` to `text-lg` for a list row):
  `font-bold text-primary`.
- Run the full suite after every task: `npm test` (= `vitest run`) from `frontend/`. Must stay green
  throughout — no task may leave the suite red for a later task to fix.
- This work is tracked via Gas Town beads `aft-92n`/`aft-a64`/`aft-jia`/`aft-lct`/`aft-a22` under
  convoy `hq-cv-9wiwh` (file-and-forget pattern — no status-sync during implementation; closing them
  is a separate step after this plan lands on `main`, not part of any task here).

---

### Task 1: Per-rep score rows get the type-scale treatment

**Files:**
- Modify: `frontend/src/components/attempt-result.tsx:26-46` (the `result.reps.map(...)` list)
- Test: `frontend/tests/unit/components/attempt-result.test.tsx`

**Interfaces:** None consumed from other tasks. Produces nothing other tasks depend on — this task
is fully self-contained.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/unit/components/attempt-result.test.tsx`, inside the existing
`describe("AttemptResult", ...)` block (after the last `it(...)`):

```tsx
  it("gives per-rep scores the same eyebrow/display type-scale as the overall score", () => {
    render(<AttemptResult result={RESULT} />);

    const repLabel = screen.getByText(/rep 1/i);
    expect(repLabel.className).toContain("text-[11px]");
    expect(repLabel.className).toContain("uppercase");
    expect(repLabel.className).toContain("tracking-wide");

    const repScore = screen.getByText(/90/);
    expect(repScore.className).toContain("text-lg");
    expect(repScore.className).toContain("font-bold");
    expect(repScore.className).toContain("text-primary");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/components/attempt-result.test.tsx` (from `frontend/`)
Expected: FAIL — the new test's `className` assertions fail because `Rep 1` and `90 / 100` currently
render as plain unstyled `<span>`s (no `text-[11px]`/`text-lg` etc. present).

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/components/attempt-result.tsx`, replace the rep row's inner `<div>` (currently
lines 29-32, the `flex justify-between` div with the plain `Rep {rep.rep_index}` / `{rep.score} /
100` spans):

```tsx
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Rep {rep.rep_index}
              </span>
              <span className="text-lg font-bold text-primary">
                {rep.score}{" "}
                <span className="text-xs font-normal text-muted-foreground">/ 100</span>
              </span>
            </div>
```

(The surrounding `<li key={rep.rep_index} className="rounded border p-2">` and the
`rep.errors.length > 0 && (...)` block below it are unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/components/attempt-result.test.tsx` (from `frontend/`)
Expected: PASS — all tests in the file, including the new one and the 5 pre-existing ones
(overall score, rep list, video, form-error copy, no-errors case).

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add frontend/src/components/attempt-result.tsx frontend/tests/unit/components/attempt-result.test.tsx
git commit -m "style(frontend): give per-rep score rows the eyebrow/display type-scale treatment"
```

---

### Task 2: `AttemptDetailContent` wraps once, at one width

**Files:**
- Modify: `frontend/src/app/attempts/[id]/page.tsx` (the whole `AttemptDetailContent` function body,
  lines 24-77)
- Test: `frontend/tests/unit/app/attempt-detail-page.test.tsx`

**Interfaces:** None consumed from other tasks. Produces nothing other tasks depend on.

- [ ] **Step 1: Write the failing tests**

Replace the full contents of `frontend/tests/unit/app/attempt-detail-page.test.tsx` with:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ invalidateQueries: vi.fn() }) }));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, logout: vi.fn() }),
}));

const mockUseAttempt = vi.fn();
vi.mock("@/hooks/use-attempt", () => ({ useAttempt: () => mockUseAttempt() }));

import { AttemptDetailContent } from "@/app/attempts/[id]/page";

describe("AttemptDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the AppShell wordmark even while the attempt is loading", () => {
    mockUseAttempt.mockReturnValue({ data: undefined, isLoading: true, error: null });

    render(<AttemptDetailContent attemptId="a1" />);

    expect(screen.getByText("AI Fitness Trainer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });

  it("aligns the loading state to the same content width as the loaded state", () => {
    mockUseAttempt.mockReturnValue({ data: undefined, isLoading: true, error: null });

    render(<AttemptDetailContent attemptId="a1" />);

    expect(screen.getByText(/loading/i).parentElement?.className).toContain("max-w-2xl");
  });

  it("aligns the error state to the same content width as the loaded state", () => {
    mockUseAttempt.mockReturnValue({ data: undefined, isLoading: false, error: new Error("boom") });

    render(<AttemptDetailContent attemptId="a1" />);

    expect(screen.getByText(/could not load this attempt/i).parentElement?.className).toContain(
      "max-w-2xl",
    );
  });
});
```

Note: this restructures the file's mocks from a static `vi.mock` factory (fixed `isLoading: true`)
to a `mockUseAttempt` reference so each test can set its own return value — the pre-existing loading
test is kept, just adapted to the new mock shape, plus 2 new tests for the width-alignment bug.

**Why no separate "single AppShell wrap" test:** the wrap-inconsistency finding (3 separate
`<AppShell>` call sites vs. 1) has no observable runtime symptom on its own — React only ever
renders one of the three branches at a time either way, before or after the fix. Its only *testable*
symptom is the width mismatch above, which the 2 new tests already cover with a real red→green
cycle. The wrap consolidation itself (Step 3) is verified by reading the diff, not a redundant test
that would pass unchanged before and after.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `npx vitest run tests/unit/app/attempt-detail-page.test.tsx` (from `frontend/`)
Expected: the pre-existing wordmark test PASSes (mock shape change doesn't affect it), the 2 new
width-alignment tests FAIL — current code renders loading/error text in a bare `<p className="p-6">`
with no `max-w-2xl` ancestor.

- [ ] **Step 3: Write minimal implementation**

Replace `frontend/src/app/attempts/[id]/page.tsx` in full:

```tsx
"use client";

import { use, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ProtectedRoute } from "@/components/protected-route";
import { AttemptResult } from "@/components/attempt-result";
import { AppShell } from "@/components/app-shell";
import { useAttempt } from "@/hooks/use-attempt";
import { apiFetch } from "@/lib/api-client";
import { failureMessage } from "@/lib/failure-messages";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";

export default function AttemptDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <ProtectedRoute>
      <AttemptDetailContent attemptId={id} />
    </ProtectedRoute>
  );
}

export function AttemptDetailContent({ attemptId }: { attemptId: string }) {
  const { data, isLoading, error } = useAttempt(attemptId);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete() {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      const response = await apiFetch(`/v1/attempts/${attemptId}`, { method: "DELETE" });
      if (response.status !== 204) throw new Error("delete failed");
      await queryClient.invalidateQueries({ queryKey: ["attempts"] });
      router.push("/");
    } catch {
      setDeleteError("Could not delete this attempt. Try again.");
      setIsDeleting(false);
    }
  }

  let content: ReactNode;
  if (isLoading) {
    content = <p>Loading...</p>;
  } else if (error || !data) {
    content = <p>Could not load this attempt.</p>;
  } else {
    content = (
      <>
        <h1 className="text-2xl font-semibold">Attempt</h1>
        <p className="text-muted-foreground">Status: {data.status}</p>

        {(data.status === "queued" || data.status === "processing") && (
          <p>Analyzing your video — this page updates automatically.</p>
        )}

        {data.status === "failed" && data.error && (
          <Alert variant="destructive">
            <AlertDescription>{failureMessage(data.error.code)}</AlertDescription>
          </Alert>
        )}

        {data.status === "completed" && data.result && <AttemptResult result={data.result} />}

        {deleteError && (
          <Alert variant="destructive">
            <AlertDescription>{deleteError}</AlertDescription>
          </Alert>
        )}
        <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
          {isDeleting ? "Deleting..." : "Delete this attempt"}
        </Button>
      </>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-4 p-6">{content}</div>
    </AppShell>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/unit/app/attempt-detail-page.test.tsx` (from `frontend/`)
Expected: PASS — all 3 tests.

- [ ] **Step 5: Run the full suite (this task touches a shared page component)**

Run: `npm test` (from `frontend/`)
Expected: PASS — no regressions in other suites that render this page or `AttemptResult`.

- [ ] **Step 6: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add "frontend/src/app/attempts/[id]/page.tsx" frontend/tests/unit/app/attempt-detail-page.test.tsx
git commit -m "fix(frontend): wrap AttemptDetailContent in AppShell once, at one content width"
```

---

### Task 3: `AppShell` wordmark becomes a link back to `/`

**Files:**
- Modify: `frontend/src/components/app-shell.tsx`
- Test: `frontend/tests/unit/components/app-shell.test.tsx`

**Interfaces:** None consumed from other tasks. Produces nothing other tasks depend on.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/unit/components/app-shell.test.tsx`, inside the existing
`describe("AppShell", ...)` block:

```tsx
  it("renders the wordmark as a link back to /", () => {
    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );

    const wordmark = screen.getByRole("link", { name: "AI Fitness Trainer" });
    expect(wordmark).toHaveAttribute("href", "/");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/components/app-shell.test.tsx` (from `frontend/`)
Expected: FAIL — `getByRole("link", { name: "AI Fitness Trainer" })` finds no matching element,
since the wordmark is currently a plain `<span>`.

- [ ] **Step 3: Write minimal implementation**

Replace `frontend/src/components/app-shell.tsx` in full:

```tsx
"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

export function AppShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth();

  return (
    <div className="min-h-full">
      <header className="border-b border-border bg-card px-6 py-3">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <Link href="/" className="text-base font-semibold">
            AI Fitness Trainer
          </Link>
          <Button variant="ghost" size="sm" onClick={() => logout()}>
            Log out
          </Button>
        </div>
      </header>
      {children}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/components/app-shell.test.tsx` (from `frontend/`)
Expected: PASS — both tests in the file.

- [ ] **Step 5: Run the full suite (AppShell is used on every authenticated page)**

Run: `npm test` (from `frontend/`)
Expected: PASS — no regressions on pages that assert on the wordmark text (they query by text, not
by tag, so the `<span>` → `<Link>` swap doesn't break them; confirmed by Task 2's own wordmark test).

- [ ] **Step 6: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add frontend/src/components/app-shell.tsx frontend/tests/unit/components/app-shell.test.tsx
git commit -m "fix(frontend): make the AppShell wordmark a link back to /"
```

---

### Task 4: `STATUS_PILL_CLASSES` gets a fallback for unrecognized statuses

**Files:**
- Modify: `frontend/src/components/attempt-history-list.tsx:11-16`
- Test: `frontend/tests/unit/components/attempt-history-list.test.tsx`

**Interfaces:** None consumed from other tasks. Produces nothing other tasks depend on.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/unit/components/attempt-history-list.test.tsx`, inside the existing
`describe("AttemptHistoryList", ...)` block (after the last `it(...)`):

```tsx
  it("falls back to a neutral pill style for a status outside the known set", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          items: [
            { attempt_id: "a1", exercise_type: "squat", status: "unknown", overall_score: null, created_at: "2026-08-04T10:00:00Z" },
          ],
          next_cursor: null,
        }),
        { status: 200 },
      ),
    );

    render(<AttemptHistoryList />, { wrapper });

    const pill = await screen.findByText("unknown");
    expect(pill.className).toContain("bg-muted");
    expect(pill.className).toContain("text-muted-foreground");
  });
```

This simulates the real failure mode honestly: `"unknown"` arrives as a plain string through the
mocked HTTP response's JSON body, exactly like a real backend response would, rather than bypassing
TypeScript with an `as` cast on an in-memory object.

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/components/attempt-history-list.test.tsx` (from `frontend/`)
Expected: FAIL — `STATUS_PILL_CLASSES["unknown"]` is `undefined` today, so the pill's `className`
does not contain `bg-muted`/`text-muted-foreground` (the interpolated `undefined` renders as the
literal string `"undefined"` in the class list instead).

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/components/attempt-history-list.tsx`, add a fallback constant after
`STATUS_PILL_CLASSES` (currently lines 11-16) and use it at the lookup site (currently line 50):

```tsx
const STATUS_PILL_CLASSES: Record<AttemptSummary["status"], string> = {
  queued: "bg-muted text-muted-foreground",
  processing: "bg-muted text-muted-foreground",
  completed: "bg-primary/10 text-primary",
  failed: "bg-destructive/10 text-destructive",
};
const DEFAULT_STATUS_PILL_CLASS = "bg-muted text-muted-foreground";
```

And change the interpolation:

```tsx
              className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_PILL_CLASSES[attempt.status] ?? DEFAULT_STATUS_PILL_CLASS}`}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/components/attempt-history-list.test.tsx` (from `frontend/`)
Expected: PASS — all tests in the file, including the new one and the 4 pre-existing ones.

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add frontend/src/components/attempt-history-list.tsx frontend/tests/unit/components/attempt-history-list.test.tsx
git commit -m "fix(frontend): fall back to a neutral status-pill style for unrecognized statuses"
```

---

### Final step: full-suite verification

- [ ] Run: `npm test` (from `frontend/`)
  Expected: PASS — full suite green (56 pre-existing + 5 new = 61 tests).
- [ ] Run: `npm run lint` (from `frontend/`)
  Expected: clean, no errors or warnings.
- [ ] Run: `npm run build` (from `frontend/`)
  Expected: clean production build (catches any type errors the unit tests wouldn't, e.g. in the
  `ReactNode` typing introduced in Task 2).
