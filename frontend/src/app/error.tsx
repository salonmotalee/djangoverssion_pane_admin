"use client";
import { ErrorState } from "@/components/ui";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="session-loading">
      <ErrorState
        error="یک خطای غیرمنتظره رخ داد. دوباره تلاش کنید."
        retry={reset}
      />
    </main>
  );
}
