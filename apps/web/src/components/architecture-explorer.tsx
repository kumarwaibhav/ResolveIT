"use client";

import { AnimatePresence, motion } from "motion/react";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { useState } from "react";

import { STAGES } from "@/components/viz/pipeline";
import { cn } from "@/lib/utils";

export function ArchitectureExplorer() {
  const [selected, setSelected] = useState(3);
  const reduce = useReducedMotion();
  const current = STAGES[selected]!;
  return (
    <section className="surface-panel overflow-hidden">
      <p className="eyebrow">System explorer</p>
      <h2 className="panel-title">Trace the decision path</h2>
      <p className="panel-copy">Every ticket passes the same five stages. Select one to see what it guarantees.</p>
      <div className="relative mt-6" role="group" aria-label="Explore pipeline stage">
        <svg aria-hidden="true" className="pointer-events-none absolute left-[10%] right-[10%] top-[34px] hidden h-1 w-[80%] sm:block" viewBox="0 0 100 2" preserveAspectRatio="none">
          <line x1="0" y1="1" x2="100" y2="1" stroke="var(--border)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          <motion.line
            x1="0"
            y1="1"
            y2="1"
            stroke="var(--signal)"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
            initial={false}
            animate={{ x2: (selected / (STAGES.length - 1)) * 100 }}
            transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 200, damping: 30 }}
          />
        </svg>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {STAGES.map((stage, idx) => {
            const on = selected === idx;
            const Icon = stage.Icon;
            return (
              <button
                key={stage.name}
                type="button"
                onClick={() => setSelected(idx)}
                aria-pressed={on}
                className={cn(
                  "group relative flex min-h-[7.5rem] flex-col items-center gap-3 rounded-2xl border bg-card/60 p-4 text-center transition-all hover:-translate-y-0.5",
                  on && "border-signal/60 bg-card shadow-[0_12px_32px_-12px_var(--glow)]",
                )}
              >
                <span className={cn("relative z-10 grid size-11 place-items-center rounded-xl border bg-card transition-colors", on && "border-transparent bg-primary text-primary-foreground")}>
                  <Icon aria-hidden="true" className="size-5" />
                </span>
                <span className="font-mono text-[10px] text-muted-foreground">{String(idx + 1).padStart(2, "0")}</span>
                <strong className="-mt-2 text-sm font-semibold">{stage.name}</strong>
              </button>
            );
          })}
        </div>
      </div>
      <div className="mt-6 border-t pt-5" aria-live="polite">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={current.name}
            initial={reduce ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? { opacity: 1 } : { opacity: 0, y: -6 }}
            transition={{ duration: 0.2 }}
          >
            <h3 className="text-lg font-bold tracking-[-0.02em]">{current.title}</h3>
            <p className="panel-copy mt-1 max-w-3xl">{current.detail}</p>
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  );
}
