"use client";

import { Button } from "@/components/ui/button";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div role="alert" className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-xl font-semibold">The service did not respond</h1>
      <p className="text-sm text-muted-foreground">Nothing you entered was lost on our side. Try again in a moment.</p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
