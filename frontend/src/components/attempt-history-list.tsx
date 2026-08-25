"use client";

import { useState } from "react";
import Link from "next/link";
import { useAttempts } from "@/hooks/use-attempts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { AttemptSummary } from "@/lib/types";

const DEFAULT_STATUS_PILL_CLASSES = "bg-muted text-muted-foreground";

const STATUS_PILL_CLASSES: Record<AttemptSummary["status"], string> = {
  queued: DEFAULT_STATUS_PILL_CLASSES,
  processing: DEFAULT_STATUS_PILL_CLASSES,
  completed: "bg-primary/10 text-primary-text",
  failed: "bg-destructive/10 text-destructive",
};

export function AttemptHistoryList() {
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [accumulated, setAccumulated] = useState<AttemptSummary[]>([]);
  const currentCursor = cursors[cursors.length - 1];
  const { data, isLoading, isError } = useAttempts(currentCursor);

  function handleLoadMore() {
    if (data?.items && data.next_cursor) {
      setAccumulated((prev) => [...prev, ...data.items]);
      setCursors((prev) => [...prev, data.next_cursor]);
    }
  }

  const items = [...accumulated, ...(data?.items ?? [])];

  if (isLoading && items.length === 0) return <p>Loading history...</p>;

  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Could not load your attempt history. Try again.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((attempt) => (
        <Link key={attempt.attempt_id} href={`/attempts/${attempt.attempt_id}`}>
          <Card className="flex items-center justify-between p-3 transition-colors hover:bg-muted/50">
            <span className="text-sm font-medium capitalize">{attempt.exercise_type}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${STATUS_PILL_CLASSES[attempt.status] ?? DEFAULT_STATUS_PILL_CLASSES}`}
            >
              {attempt.status}
            </span>
            <span className="text-lg font-semibold">{attempt.overall_score ?? "-"}</span>
          </Card>
        </Link>
      ))}
      {data?.next_cursor && (
        <Button variant="outline" onClick={handleLoadMore}>
          Load more
        </Button>
      )}
    </div>
  );
}
