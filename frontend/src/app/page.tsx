"use client";

import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";
import { AppShell } from "@/components/app-shell";
import { VideoUploadForm } from "@/components/video-upload-form";
import { AttemptHistoryList } from "@/components/attempt-history-list";

export default function HomePage() {
  return (
    <ProtectedRoute>
      <HomeContent />
    </ProtectedRoute>
  );
}

function HomeContent() {
  const router = useRouter();

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-8 p-6">
        <h1 className="text-2xl font-semibold">Your attempts</h1>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">Upload a new video</h2>
          <VideoUploadForm onUploaded={(attemptId) => router.push(`/attempts/${attemptId}`)} />
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-medium">History</h2>
          <AttemptHistoryList />
        </section>
      </div>
    </AppShell>
  );
}
