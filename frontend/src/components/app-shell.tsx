"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // next-themes' documented pattern for detecting client-mount to avoid an SSR/hydration mismatch
  // on resolvedTheme; the effect fires once and only affects this small leaf component, not a
  // cascading-render risk here.
  useEffect(() => {
    setMounted(true); // eslint-disable-line react-hooks/set-state-in-effect
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

function DeleteAccountControl() {
  const { deleteAccount } = useAuth();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function cancel() {
    setConfirming(false);
    setConfirmText("");
    setError(null);
  }

  async function confirm() {
    setIsDeleting(true);
    setError(null);
    try {
      await deleteAccount();
      router.push("/login");
    } catch {
      setError("Could not delete the account. Try again.");
      setIsDeleting(false);
    }
  }

  if (!confirming) {
    return (
      <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
        Delete account
      </Button>
    );
  }

  return (
    <div className="absolute right-6 top-14 z-10 w-72 space-y-3 rounded-md border border-border bg-card p-4 shadow-md">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <p className="text-sm text-muted-foreground">
        This permanently deletes your account and every video/analysis in it. This cannot be
        undone.
      </p>
      <div className="space-y-1">
        <Label htmlFor="delete-confirm">Type DELETE to confirm</Label>
        <Input
          id="delete-confirm"
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
        />
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={cancel}>
          Cancel
        </Button>
        <Button
          variant="destructive"
          size="sm"
          disabled={confirmText !== "DELETE" || isDeleting}
          onClick={confirm}
        >
          Confirm
        </Button>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { logout } = useAuth();

  return (
    <div className="min-h-full">
      <header className="relative border-b border-border bg-card px-6 py-3">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <Link href="/" className="text-base font-semibold">
            AI Fitness Trainer
          </Link>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <DeleteAccountControl />
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
