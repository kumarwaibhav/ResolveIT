import type { ReactNode } from "react";

import { ScrollReveal } from "@/components/motion";
import { cn } from "@/lib/utils";

/** A full-bleed Obsidian sheet with rounded corners. Children inherit the dark tokens. */
export function InkSheet({ children, className, id, labelledBy }: { children: ReactNode; className?: string; id?: string; labelledBy?: string }) {
  return (
    <section id={id} aria-labelledby={labelledBy} className={cn("dark sheet-ink mx-2 scroll-mt-20 rounded-[28px] sm:mx-3 sm:rounded-[40px]", className)}>
      <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8 sm:py-28">{children}</div>
    </section>
  );
}

/** Headline on the left, the plain-language point on the right. */
export function SplitHead({ id, title, sub, eyebrow, children }: { id: string; title: ReactNode; sub?: ReactNode; eyebrow?: string; children?: ReactNode }) {
  return (
    <ScrollReveal className="grid gap-6 lg:grid-cols-2 lg:items-end lg:gap-16">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2 id={id} className="text-[clamp(2.1rem,4.6vw,3.6rem)] font-semibold leading-[1.02] tracking-[-0.045em] text-balance">
          {title}
        </h2>
      </div>
      {sub || children ? (
        <div className="max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
          {sub}
          {children}
        </div>
      ) : null}
    </ScrollReveal>
  );
}
