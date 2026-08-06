import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { AttemptDetail } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

async function fetchAttempt(attemptId: string): Promise<AttemptDetail> {
  const response = await apiFetch(`/v1/attempts/${attemptId}`);
  if (!response.ok) {
    throw new Error(`failed to load attempt ${attemptId}: ${response.status}`);
  }
  return (await response.json()) as AttemptDetail;
}

export function useAttempt(attemptId: string) {
  return useQuery({
    queryKey: ["attempt", attemptId],
    queryFn: () => fetchAttempt(attemptId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const isTerminal = status === "completed" || status === "failed";
      return isTerminal ? false : POLL_INTERVAL_MS;
    },
  });
}
