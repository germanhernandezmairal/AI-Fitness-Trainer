# Frontend Design Polish Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retheme the frontend from shadcn's default grayscale palette to a warm off-white + cornflower-blue visual system, add shared site chrome (a header with logo + logout), and polish the four existing pages — with zero changes to behavior, routing, or data flow.

**Architecture:** Every shadcn component (`Button`, `Card`, `Input`, `Label`, `Alert`) already reads its colors exclusively from CSS custom properties in `frontend/src/app/globals.css`. Retheming is therefore a token-value edit, not a component-code change. On top of that, one new purely-presentational component (`AppShell`) adds a shared header to the two authenticated pages, and each page/component gets a small targeted restyle. No new dependencies, no new API calls, no new state.

**Tech Stack:** Next.js 16 (App Router), Tailwind CSS v4, shadcn/ui (Base UI primitives), Vitest + React Testing Library.

## Global Constraints

- **No behavior changes.** Every interaction, API call, error path, loading/empty state, and piece of component state must remain exactly as implemented in frontend-v1. This pass is markup/class-level styling plus one new presentational component.
- **No new dependencies.** The file input is styled with Tailwind's `file:` pseudo-element variant on the existing native `<input type="file">` — no new library.
- **Dark mode is out of scope.** Do not touch the `.dark { ... }` block in `globals.css`.
- **Font stays Geist.** No font swap, no new font import.
- **Exact palette** (replaces the existing zero-chroma tokens in `globals.css`, same variable names):
  - `--background: #fafaf9`
  - `--foreground: #1a1a1a`
  - `--card: #ffffff`
  - `--card-foreground: #1a1a1a`
  - `--popover: #ffffff`
  - `--popover-foreground: #1a1a1a`
  - `--primary: #4f7cf6`
  - `--primary-foreground: #ffffff`
  - `--secondary: #f0efec`
  - `--secondary-foreground: #1a1a1a`
  - `--muted: #f0efec`
  - `--muted-foreground: #8a8a85`
  - `--accent: #f0efec`
  - `--accent-foreground: #1a1a1a`
  - `--border: #e8e6e1`
  - `--input: #e8e6e1`
  - `--ring: #4f7cf6`
  - `--destructive`: **unchanged** — keep the existing `oklch(0.577 0.245 27.325)`, it already reads fine against the new background.
  - `--radius: 0.75rem` (was `0.625rem`).
  - `--chart-*` and `--sidebar-*` tokens: **unchanged** — nothing in the app currently renders a chart or sidebar.
- **Type scale** (use these exact utility class strings everywhere they apply, for consistency across tasks):
  - Eyebrow label: `text-[11px] font-medium uppercase tracking-wide text-muted-foreground`
  - Page title: `text-2xl font-semibold` (already used on the home and attempt-detail pages; login/register need to be brought up to it from `text-xl`)
  - Display number: `text-4xl font-bold text-primary`

---

### Task 1: Retheme design tokens

**Files:**
- Modify: `frontend/src/app/globals.css:51-75` (the `:root` block)

**Interfaces:**
- Consumes: nothing (CSS-only change).
- Produces: the palette values listed in Global Constraints, available to every component via the existing `var(--token-name)` mechanism. No component code changes anywhere depend on this task beyond what's already wired.

This is a pure CSS-value edit with no new logic to unit-test, so instead of a TDD cycle this task is verified by confirming the existing suite still passes and the app still builds with the new values.

- [ ] **Step 1: Run the full test suite to record the passing baseline**

Run: `cd frontend && npm test`
Expected: all existing tests PASS (this is the baseline — the retheme must not break it).

- [ ] **Step 2: Edit the `:root` token block**

Replace lines 51-75 of `frontend/src/app/globals.css` (everything from `:root {` through the line before `--sidebar: oklch(0.985 0 0);`) with:

```css
:root {
  --background: #fafaf9;
  --foreground: #1a1a1a;
  --card: #ffffff;
  --card-foreground: #1a1a1a;
  --popover: #ffffff;
  --popover-foreground: #1a1a1a;
  --primary: #4f7cf6;
  --primary-foreground: #ffffff;
  --secondary: #f0efec;
  --secondary-foreground: #1a1a1a;
  --muted: #f0efec;
  --muted-foreground: #8a8a85;
  --accent: #f0efec;
  --accent-foreground: #1a1a1a;
  --destructive: oklch(0.577 0.245 27.325);
  --border: #e8e6e1;
  --input: #e8e6e1;
  --ring: #4f7cf6;
  --chart-1: oklch(0.87 0 0);
  --chart-2: oklch(0.556 0 0);
  --chart-3: oklch(0.439 0 0);
  --chart-4: oklch(0.371 0 0);
  --chart-5: oklch(0.269 0 0);
  --radius: 0.75rem;
```

Leave `--sidebar*` lines (currently right after `--radius`) and the entire `.dark { ... }` block below it untouched.

- [ ] **Step 3: Run the full test suite again**

Run: `cd frontend && npm test`
Expected: same PASS result as Step 1 — a CSS token change should not affect any test outcome. If anything now fails, a test was relying on the old grayscale values (unlikely, but stop and investigate rather than proceeding).

- [ ] **Step 4: Confirm the app still builds**

Run: `cd frontend && npm run build`
Expected: build succeeds with no Tailwind/CSS errors (confirms the new hex values are valid alongside the untouched `oklch()` destructive/dark values).

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/app/globals.css
git commit -m "style(frontend): retheme to off-white + cornflower-blue palette"
```

---

### Task 2: Build the `AppShell` component

**Files:**
- Create: `frontend/src/components/app-shell.tsx`
- Test: `frontend/tests/unit/components/app-shell.test.tsx`

**Interfaces:**
- Consumes: `useAuth()` from `@/lib/auth-context` (specifically its `logout(): Promise<void>`), `Button` from `@/components/ui/button`.
- Produces: `AppShell({ children: ReactNode })` — a React component. Tasks 3 and 4 wrap their page content with `<AppShell>...</AppShell>`.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/components/app-shell.test.tsx`:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const mockLogout = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ logout: mockLogout }) }));

import { AppShell } from "@/components/app-shell";

describe("AppShell", () => {
  afterEach(() => {
    cleanup();
    mockLogout.mockReset();
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
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/components/app-shell.test.tsx`
Expected: FAIL with a module-not-found error for `@/components/app-shell`.

- [ ] **Step 3: Write the implementation**

Create `frontend/src/components/app-shell.tsx`:

```tsx
"use client";

import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

export function AppShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth();

  return (
    <div className="min-h-full">
      <header className="border-b border-border bg-card px-6 py-3">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <span className="text-base font-semibold">AI Fitness Trainer</span>
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

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/components/app-shell.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/components/app-shell.tsx tests/unit/components/app-shell.test.tsx
git commit -m "feat(frontend): add AppShell header component"
```

---

### Task 3: Wire `AppShell` into the home page

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Test: `frontend/tests/unit/app/home-page.test.tsx` (new — no unit test currently exists for this page, only the e2e suite covers it)

**Interfaces:**
- Consumes: `AppShell` from `@/components/app-shell` (Task 2).
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/app/home-page.test.tsx`:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, logout: vi.fn() }),
}));
vi.mock("@/components/video-upload-form", () => ({
  VideoUploadForm: () => <div>upload form</div>,
}));
vi.mock("@/components/attempt-history-list", () => ({
  AttemptHistoryList: () => <div>history list</div>,
}));

import HomePage from "@/app/page";

describe("HomePage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the AppShell wordmark, page title, and both sections", () => {
    render(<HomePage />);

    expect(screen.getByText("AI Fitness Trainer")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /your attempts/i })).toBeInTheDocument();
    expect(screen.getByText("upload form")).toBeInTheDocument();
    expect(screen.getByText("history list")).toBeInTheDocument();
  });

  it("renders a working log out control", () => {
    render(<HomePage />);

    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/app/home-page.test.tsx`
Expected: FAIL — no "AI Fitness Trainer" wordmark is rendered yet (the current page has no `AppShell`).

- [ ] **Step 3: Update the page**

In `frontend/src/app/page.tsx`, replace the whole file with:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";
import { AppShell } from "@/components/app-shell";
import { VideoUploadForm } from "@/components/video-upload-form";
import { AttemptHistoryList } from "@/components/attempt-history-list";

export default function HomePage() {
  return (
    <ProtectedRoute>
      <HomeContent />
    </ProtectedRoute>
  );
}

function HomeContent() {
  const router = useRouter();

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-8 p-6">
        <h1 className="text-2xl font-semibold">Your attempts</h1>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">Upload a new video</h2>
          <VideoUploadForm onUploaded={(attemptId) => router.push(`/attempts/${attemptId}`)} />
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">History</h2>
          <AttemptHistoryList />
        </section>
      </div>
    </AppShell>
  );
}
```

This removes the now-unused `useAuth` and `Button` imports (logout moved into `AppShell`) and the ad hoc header row.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/app/home-page.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full unit suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: all tests PASS, including `tests/unit/components/protected-route.test.tsx` (unaffected — `ProtectedRoute` itself wasn't touched).

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/app/page.tsx tests/unit/app/home-page.test.tsx
git commit -m "feat(frontend): wire AppShell into the home page"
```

---

### Task 4: Wire `AppShell` into the attempt-detail page

**Files:**
- Modify: `frontend/src/app/attempts/[id]/page.tsx`
- Test: `frontend/tests/unit/app/attempt-detail-page.test.tsx` (new — no unit test currently exists for this page)

**Interfaces:**
- Consumes: `AppShell` from `@/components/app-shell` (Task 2).
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/unit/app/attempt-detail-page.test.tsx`:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ invalidateQueries: vi.fn() }) }));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, logout: vi.fn() }),
}));
vi.mock("@/hooks/use-attempt", () => ({
  useAttempt: () => ({ data: undefined, isLoading: true, error: null }),
}));

import AttemptDetailPage from "@/app/attempts/[id]/page";

describe("AttemptDetailPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the AppShell wordmark even while the attempt is loading", () => {
    render(<AttemptDetailPage params={Promise.resolve({ id: "a1" })} />);

    expect(screen.getByText("AI Fitness Trainer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/app/attempt-detail-page.test.tsx`
Expected: FAIL — no "AI Fitness Trainer" wordmark rendered yet.

- [ ] **Step 3: Update the page**

In `frontend/src/app/attempts/[id]/page.tsx`, replace the `AttemptDetailContent` function (lines 23-74) with:

```tsx
function AttemptDetailContent({ attemptId }: { attemptId: string }) {
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

  if (isLoading) return <AppShell><p className="p-6">Loading...</p></AppShell>;
  if (error || !data) return <AppShell><p className="p-6">Could not load this attempt.</p></AppShell>;

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-4 p-6">
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
      </div>
    </AppShell>
  );
}
```

And add the import at the top of the file, alongside the other `@/components/*` imports:

```tsx
import { AppShell } from "@/components/app-shell";
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/app/attempt-detail-page.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full unit suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/app/attempts/[id]/page.tsx tests/unit/app/attempt-detail-page.test.tsx
git commit -m "feat(frontend): wire AppShell into the attempt-detail page"
```

---

### Task 5: Standardize the login/register page-title size

**Files:**
- Modify: `frontend/src/app/login/page.tsx:43`
- Modify: `frontend/src/app/register/page.tsx:49`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new consumed by later tasks.

Both headings currently use `text-xl font-semibold`; the type scale in Global Constraints standardizes page titles to `text-2xl font-semibold` (already true on the home and attempt-detail pages since Tasks 3-4). The existing tests for both pages match on role/name (`getByRole("button", ...)`, `getByLabelText(...)`) and never assert on heading size, so no test changes are needed — the existing suites are the regression check.

- [ ] **Step 1: Run the existing tests for both pages to record the passing baseline**

Run: `cd frontend && npx vitest run tests/unit/app/login-page.test.tsx tests/unit/app/register-page.test.tsx`
Expected: all PASS (baseline).

- [ ] **Step 2: Update the login page heading**

In `frontend/src/app/login/page.tsx`, change line 43 from:

```tsx
        <h1 className="text-xl font-semibold">Log in</h1>
```

to:

```tsx
        <h1 className="text-2xl font-semibold">Log in</h1>
```

- [ ] **Step 3: Update the register page heading**

In `frontend/src/app/register/page.tsx`, change line 49 from:

```tsx
        <h1 className="text-xl font-semibold">Create account</h1>
```

to:

```tsx
        <h1 className="text-2xl font-semibold">Create account</h1>
```

- [ ] **Step 4: Run the tests again to confirm no regressions**

Run: `cd frontend && npx vitest run tests/unit/app/login-page.test.tsx tests/unit/app/register-page.test.tsx`
Expected: same PASS result as Step 1.

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/app/login/page.tsx src/app/register/page.tsx
git commit -m "style(frontend): standardize login/register page-title size"
```

---

### Task 6: Style the video file input

**Files:**
- Modify: `frontend/src/components/video-upload-form.tsx:85-90`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new consumed by later tasks.

Purely cosmetic — the native `<input type="file">` element, its `id`, `onChange` handler, and `accept` attribute are unchanged, so `getByLabelText(/video file/i)` and the existing `uploadFileToInput` test helper in `tests/unit/components/video-upload-form.test.tsx` are unaffected. That existing suite is the regression check; no new test is added for a styling-only change with no new behavior.

- [ ] **Step 1: Run the existing test file to record the passing baseline**

Run: `cd frontend && npx vitest run tests/unit/components/video-upload-form.test.tsx`
Expected: all 5 tests PASS (baseline).

- [ ] **Step 2: Style the input**

In `frontend/src/components/video-upload-form.tsx`, change:

```tsx
        <input
          id="video-file"
          type="file"
          accept="video/mp4,video/quicktime"
          onChange={handleFileChange}
        />
```

to:

```tsx
        <input
          id="video-file"
          type="file"
          accept="video/mp4,video/quicktime"
          onChange={handleFileChange}
          className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-primary file:px-3 file:py-2 file:text-sm file:font-medium file:text-primary-foreground file:transition-colors hover:file:bg-primary/90"
        />
```

- [ ] **Step 3: Run the test file again to confirm no regressions**

Run: `cd frontend && npx vitest run tests/unit/components/video-upload-form.test.tsx`
Expected: same PASS result as Step 1.

- [ ] **Step 4: Commit**

```bash
cd frontend
git add src/components/video-upload-form.tsx
git commit -m "style(frontend): style the video file input"
```

---

### Task 7: Restyle the attempt history list rows

**Files:**
- Modify: `frontend/src/components/attempt-history-list.tsx`
- Test: `frontend/tests/unit/components/attempt-history-list.test.tsx` (extend with one new test; existing tests are untouched)

**Interfaces:**
- Consumes: `AttemptStatus` from `@/lib/types` (already imported transitively via `AttemptSummary`).
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Add this test to the existing `describe("AttemptHistoryList", ...)` block in `frontend/tests/unit/components/attempt-history-list.test.tsx` (after the last existing `it(...)`, before the closing `});`):

```tsx
  it("gives each status a distinct pill style", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          items: [
            { attempt_id: "a1", exercise_type: "squat", status: "completed", overall_score: 82, created_at: "2026-08-04T10:00:00Z" },
            { attempt_id: "a2", exercise_type: "squat", status: "failed", overall_score: null, created_at: "2026-08-04T09:00:00Z" },
          ],
          next_cursor: null,
        }),
        { status: 200 },
      ),
    );

    render(<AttemptHistoryList />, { wrapper });

    const completedPill = await screen.findByText("completed");
    const failedPill = screen.getByText("failed");

    expect(completedPill.className).toContain("text-primary");
    expect(failedPill.className).toContain("text-destructive");
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/components/attempt-history-list.test.tsx`
Expected: FAIL — the new test, since today's `<span>{attempt.status}</span>` has no `className` at all.

- [ ] **Step 3: Restyle the rows**

In `frontend/src/components/attempt-history-list.tsx`, add this above the `AttemptHistoryList` function:

```tsx
const STATUS_PILL_CLASSES: Record<AttemptSummary["status"], string> = {
  queued: "bg-muted text-muted-foreground",
  processing: "bg-muted text-muted-foreground",
  completed: "bg-primary/10 text-primary",
  failed: "bg-destructive/10 text-destructive",
};
```

Then replace the row markup:

```tsx
        <Link key={attempt.attempt_id} href={`/attempts/${attempt.attempt_id}`}>
          <Card className="flex justify-between p-3">
            <span>{attempt.exercise_type}</span>
            <span>{attempt.status}</span>
            <span>{attempt.overall_score ?? "-"}</span>
          </Card>
        </Link>
```

with:

```tsx
        <Link key={attempt.attempt_id} href={`/attempts/${attempt.attempt_id}`}>
          <Card className="flex items-center justify-between p-3 transition-colors hover:bg-muted/50">
            <span className="text-sm font-medium capitalize">{attempt.exercise_type}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_PILL_CLASSES[attempt.status]}`}
            >
              {attempt.status}
            </span>
            <span className="text-lg font-semibold">{attempt.overall_score ?? "-"}</span>
          </Card>
        </Link>
```

- [ ] **Step 4: Run the test file to verify everything passes**

Run: `cd frontend && npx vitest run tests/unit/components/attempt-history-list.test.tsx`
Expected: PASS (4 tests, including the new one).

- [ ] **Step 5: Commit**

```bash
cd frontend
git add src/components/attempt-history-list.tsx tests/unit/components/attempt-history-list.test.tsx
git commit -m "style(frontend): restyle attempt history rows with status pills"
```

---

### Task 8: Restyle the attempt result score card

**Files:**
- Modify: `frontend/src/components/attempt-result.tsx:13-18`
- Test: `frontend/tests/unit/components/attempt-result.test.tsx` (extend with one new test; existing tests are untouched)

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Add this test to the existing `describe("AttemptResult", ...)` block in `frontend/tests/unit/components/attempt-result.test.tsx` (after the last existing `it(...)`, before the closing `});`):

```tsx
  it("shows an eyebrow label above the overall score", () => {
    render(<AttemptResult result={RESULT} />);

    expect(screen.getByText(/overall score/i)).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/components/attempt-result.test.tsx`
Expected: FAIL — the new test, since today's score card has no "Overall score" label.

- [ ] **Step 3: Restyle the score card**

In `frontend/src/components/attempt-result.tsx`, replace:

```tsx
      <Card className="p-4">
        <p className="text-3xl font-bold">{result.overall_score} / 100</p>
        <p className="text-muted-foreground">{result.summary}</p>
      </Card>
```

with:

```tsx
      <Card className="p-4">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Overall score
        </p>
        <p className="text-4xl font-bold text-primary">
          {result.overall_score}
          <span className="text-lg font-normal text-muted-foreground"> / 100</span>
        </p>
        <p className="mt-2 text-muted-foreground">{result.summary}</p>
      </Card>
```

- [ ] **Step 4: Run the test file to verify everything passes**

Run: `cd frontend && npx vitest run tests/unit/components/attempt-result.test.tsx`
Expected: PASS (6 tests, including the new one). In particular, confirm `shows the overall score and summary` (which does `getByText(/82/)`) still passes — the score `82` remains a direct text-node child of its `<p>`, so it stays uniquely matchable even with the new sibling `<span>`.

- [ ] **Step 5: Run the full unit suite one final time**

Run: `cd frontend && npm test`
Expected: all tests PASS across the whole suite — the final confirmation that all 8 tasks compose cleanly.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/components/attempt-result.tsx tests/unit/components/attempt-result.test.tsx
git commit -m "style(frontend): restyle the attempt result score card"
```
