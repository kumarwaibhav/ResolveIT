import type { ReactNode } from "react";

import { Reveal } from "@/components/motion";
import { cn } from "@/lib/utils";

export interface HeroStat {
  label: string;
  value: ReactNode;
}

/** Subpage opener: an Obsidian sheet with the headline, one plain sentence, actions and a fact strip. */
export function PageHero({ eyebrow, title, sub, actions, stats, className }: { eyebrow: string; title: ReactNode; sub: ReactNode; actions?: ReactNode; stats?: HeroStat[]; className?: string }) {
  return (
    <section className={cn("dark sheet-ink mx-2 mt-3 rounded-[28px] sm:mx-3 sm:rounded-[40px]", className)}>
      <div className="relative mx-auto max-w-6xl overflow-hidden px-5 pb-10 pt-16 sm:px-8 sm:pb-12 sm:pt-24">
        <div aria-hidden="true" className="pointer-events-none absolute -right-24 -top-24 size-[28rem] rounded-full bg-[radial-gradient(closest-side,var(--glow),transparent)]" />
        <Reveal className="relative max-w-3xl">
          <p className="kicker">{eyebrow}</p>
          <h1 className="text-[clamp(2.4rem,6vw,4.5rem)] font-semibold leading-[1] tracking-[-0.05em] text-balance">{title}</h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">{sub}</p>
          {actions ? <div className="mt-8 flex flex-wrap gap-3">{actions}</div> : null}
        </Reveal>
        {stats?.length ? (
          <dl className="relative mt-14 grid grid-cols-2 gap-x-6 gap-y-6 border-t pt-6 sm:mt-20 lg:grid-cols-4">
            {stats.map((s) => (
              <div key={s.label}>
                <dt className="text-sm text-muted-foreground">{s.label}</dt>
                <dd className="mt-1 text-xl font-semibold tracking-[-0.02em]">{s.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </section>
  );
}
