import Link from "next/link";
import { Card } from "@/components/ui/card";

export default function PrivacyPage() {
  return (
    <Card className="mx-auto mt-16 max-w-2xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Privacy Policy</h1>

      <section className="space-y-1">
        <h2 className="text-lg font-medium">What we collect</h2>
        <p className="text-sm text-muted-foreground">
          Your account email and password (stored as a salted hash, never in plain text). Any
          video you upload, the exercise scores and joint-angle measurements our analysis
          derives from it, and an annotated copy of the video showing that analysis.
        </p>
      </section>

      <section className="space-y-1">
        <h2 className="text-lg font-medium">Why</h2>
        <p className="text-sm text-muted-foreground">
          Solely to analyze your exercise technique and show you the result — the only purpose
          this account exists for. We do not sell or share this data with third parties.
        </p>
      </section>

      <section className="space-y-1">
        <h2 className="text-lg font-medium">How long</h2>
        <p className="text-sm text-muted-foreground">
          Every video and its analysis are automatically and permanently deleted 30 days after
          upload.
        </p>
      </section>

      <section className="space-y-1">
        <h2 className="text-lg font-medium">Your rights</h2>
        <p className="text-sm text-muted-foreground">
          You can delete a single analysis at any time from your history, or delete your entire
          account (and everything in it) from the header menu — both take effect immediately.
        </p>
      </section>

      <p className="text-center text-sm text-muted-foreground">
        <Link href="/register" className="underline underline-offset-2">
          Back to registration
        </Link>
      </p>
    </Card>
  );
}
