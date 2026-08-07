"use client";

import { useState } from "react";
import Link from "next/link";
import { useAttempts } from "@/hooks/use-attempts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { AttemptSummary } from "@/lib/types";

export function AttemptHistoryList() {
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [accumulated, setAccumulated] = useState<AttemptSummary[]>([]);
  const currentCursor = cursors[cursors.length - 1];
  const { data, isLoading } = useAttempts(currentCursor);

  function handleLoadMore() {
    if (data?.items && data.next_cursor) {
      setAccumulated((prev) => [...prev, ...data.items]);
      setCursors((prev) => [...prev, data.next_cursor]);
    }
  }

  const items = [...accumulated, ...(data?.items ?? [])];

  if (isLoading && items.length === 0) return <p>Loading history...</p>;

  return (
    <div className="space-y-2">
      {items.map((attempt) => (
        <Link key={attempt.attempt_id} href={`/attempts/${attempt.attempt_id}`}>
          <Card className="flex justify-between p-3">
            <span>{attempt.exercise_type}</span>
            <span>{attempt.status}</span>
            <span>{attempt.overall_score ?? "-"}</span>
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
