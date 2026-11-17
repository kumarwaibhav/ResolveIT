import { Info } from "lucide-react";
import type { ReactNode } from "react";

import { Reveal } from "@/components/motion";

/** Page header: mono eyebrow, one big title, one plain sentence, optional actions on the right. */
export function WorkspaceHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: ReactNode }) {
  return (
    <Reveal className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl">
        <p className="eyebrow inline-flex items-center gap-2">
          <span aria-hidden="true" className="h-px w-6 bg-signal" />
          {eyebrow}
        </p>
        <h1 className="text-gradient text-[clamp(2rem,4.2vw,3.25rem)] font-bold leading-[1.04] tracking-[-0.045em]">{title}</h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted-foreground sm:text-base">{description}</p>
      </div>
      {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
    </Reveal>
  );
}

export function LocalDraftNotice() {
  return (
    <p className="local-notice">
      <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-signal" />
      Browser-only workspace. Changes stay on this device as drafts until you export them; nothing is saved to the server.
    </p>
  );
}
