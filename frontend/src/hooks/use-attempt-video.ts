import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";

interface UseAttemptVideoResult {
  blobUrl: string | null;
  isLoading: boolean;
  error: string | null;
}

export function useAttemptVideo(videoUrl: string | null): UseAttemptVideoResult {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoUrl) {
      setBlobUrl(null);
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;

    setIsLoading(true);
    setError(null);

    // videoUrl already includes the /v1/... path the backend returned; apiFetch only
    // needs the path portion, so we pass it through relative to the API base by
    // stripping the origin if present — the backend always returns same-origin-relative
    // paths in practice (see docs/superpowers/specs/2026-08-04-frontend-design.md §4).
    const path = videoUrl.replace(/^https?:\/\/[^/]+/, "");

    apiFetch(path)
      .then((response) => {
        if (!response.ok) throw new Error(`failed to load video: ${response.status}`);
        return response.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "failed to load video");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [videoUrl]);

  return { blobUrl, isLoading, error };
}
