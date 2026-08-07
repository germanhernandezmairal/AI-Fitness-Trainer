"use client";

import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";
import { VideoUploadForm } from "@/components/video-upload-form";
import { AttemptHistoryList } from "@/components/attempt-history-list";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <ProtectedRoute>
      <HomeContent />
    </ProtectedRoute>
  );
}

function HomeContent() {
  const router = useRouter();
  const { logout } = useAuth();

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Your attempts</h1>
        <Button variant="outline" onClick={() => logout()}>
          Log out
        </Button>
      </div>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Upload a new video</h2>
        <VideoUploadForm onUploaded={(attemptId) => router.push(`/attempts/${attemptId}`)} />
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">History</h2>
        <AttemptHistoryList />
      </section>
    </div>
  );
}
