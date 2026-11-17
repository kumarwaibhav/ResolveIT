import Link from "next/link";

import { MonolithMark } from "@/components/brand/monolith";

export default function NotFound() {
  return (
    <main id="main" className="relative grid min-h-dvh place-items-center px-5">
      <div className="atmosphere" aria-hidden="true" />
      <div className="glass max-w-md rounded-3xl p-8 text-center">
        <MonolithMark size={48} className="mx-auto" />
        <p className="eyebrow mt-6">404</p>
        <h1 className="text-3xl font-bold tracking-[-0.04em]">Nothing here</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">That page or incident does not exist, or it belongs to another workspace.</p>
        <Link href="/intake" className="workspace-button primary mt-6">Report a problem</Link>
      </div>
    </main>
  );
}
