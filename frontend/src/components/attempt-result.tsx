"use client";

import { useAttemptVideo } from "@/hooks/use-attempt-video";
import type { AnalysisResult } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { formErrorMessage } from "@/lib/form-error-messages";

export function AttemptResult({ result }: { result: AnalysisResult }) {
  const { blobUrl, isLoading: isVideoLoading, error: videoError } = useAttemptVideo(
    result.annotated_video_url,
  );

  return (
    <div className="space-y-4">
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

      <ul className="space-y-2">
        {result.reps.map((rep) => (
          <li key={rep.rep_index} className="rounded border p-2">
            <div className="flex justify-between">
              <span>Rep {rep.rep_index}</span>
              <span>{rep.score} / 100</span>
            </div>
            {rep.errors.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {rep.errors.map((code) => (
                  <span
                    key={code}
                    className="rounded bg-destructive/10 px-1.5 py-0.5 text-xs text-destructive"
                  >
                    {formErrorMessage(code)}
                  </span>
                ))}
              </div>
            )}
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
