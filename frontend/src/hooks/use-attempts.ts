import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { AttemptPage } from "@/lib/types";

async function fetchAttempts(cursor: string | null): Promise<AttemptPage> {
  const path = cursor ? `/v1/attempts?cursor=${encodeURIComponent(cursor)}` : "/v1/attempts";
  const response = await apiFetch(path);
  if (!response.ok) throw new Error(`failed to load history: ${response.status}`);
  return (await response.json()) as AttemptPage;
}

export function useAttempts(cursor: string | null) {
  return useQuery({
    queryKey: ["attempts", cursor],
    queryFn: () => fetchAttempts(cursor),
  });
}
