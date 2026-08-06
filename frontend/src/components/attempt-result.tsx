"use client";

import { useAttemptVideo } from "@/hooks/use-attempt-video";
import type { AnalysisResult } from "@/lib/types";
import { Card } from "@/components/ui/card";

export function AttemptResult({ result }: { result: AnalysisResult }) {
  const { blobUrl, isLoading: isVideoLoading, error: videoError } = useAttemptVideo(
    result.annotated_video_url,
  );

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <p className="text-3xl font-bold">{result.overall_score} / 100</p>
        <p className="text-muted-foreground">{result.summary}</p>
      </Card>

      <ul className="space-y-2">
        {result.reps.map((rep) => (
          <li key={rep.rep_index} className="flex justify-between rounded border p-2">
            <span>Rep {rep.rep_index}</span>
            <span>{rep.score} / 100</span>
          </li>
        ))}
      </ul>

      {blobUrl && (
        <video data-testid="annotated-video" src={blobUrl} controls className="w-full rounded" />
      )}
      {isVideoLoading && <p>Loading annotated video...</p>}
      {videoError && <p className="text-destructive">Could not load the annotated video.</p>}
    </div>
  );
}
