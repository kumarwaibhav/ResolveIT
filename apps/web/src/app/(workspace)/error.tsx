"use client";

import { RefreshCw, ServerCrash } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div role="alert" className="glass mx-auto mt-10 max-w-lg rounded-3xl p-8 text-center">
      <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-risk-surface text-risk" aria-hidden="true">
        <ServerCrash className="size-7" />
      </span>
      <h1 className="mt-5 text-2xl font-bold tracking-[-0.03em]">The service did not respond</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        The request could not be completed. If you were sending a ticket, check whether it was saved before sending it again.
      </p>
      <Button onClick={reset} className="mt-6 min-h-11 gap-2 px-5">
        <RefreshCw aria-hidden="true" className="size-4" /> Try again
      </Button>
    </div>
  );
}
