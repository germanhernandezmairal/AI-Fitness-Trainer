"use client";

import { use, useState } from "react";
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
