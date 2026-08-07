"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { uploadErrorMessage } from "@/lib/upload-error-messages";
import type { AttemptCreated, UploadErrorResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";

const ALLOWED_EXTENSIONS = [".mp4", ".mov"];
const MAX_BYTES = 104_857_600;

function hasAllowedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function VideoUploadForm({ onUploaded }: { onUploaded: (attemptId: string) => void }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setError(null);
    setFile(event.target.files?.[0] ?? null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a video file first.");
      return;
    }
    if (!hasAllowedExtension(file.name)) {
      setError(uploadErrorMessage("unsupported_format"));
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(uploadErrorMessage("file_too_large"));
      return;
    }

    setError(null);
    setIsUploading(true);
    try {
      try {
        const formData = new FormData();
        formData.append("video", file);
        formData.append("exercise_type", "squat");

        const response = await apiFetch("/v1/attempts", { method: "POST", body: formData });

        if (response.status === 202) {
          const created = (await response.json()) as AttemptCreated;
          await queryClient.invalidateQueries({ queryKey: ["attempts"] });
          onUploaded(created.attempt_id);
          return;
        }
        if (response.status === 400) {
          const body = (await response.json()) as UploadErrorResponse;
          setError(uploadErrorMessage(body.error.code));
          return;
        }
        setError("Could not upload the video. Try again.");
      } catch {
        setError("Could not upload the video. Try again.");
      }
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-1">
        <Label htmlFor="video-file">Video file</Label>
        <input
          id="video-file"
          type="file"
          accept="video/mp4,video/quicktime"
          onChange={handleFileChange}
        />
      </div>
      <Button type="submit" disabled={isUploading}>
        {isUploading ? "Uploading..." : "Upload"}
      </Button>
    </form>
  );
}
