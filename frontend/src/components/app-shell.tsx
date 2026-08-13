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
