"use client";

import { ChevronDown, Compass } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useId, useState } from "react";

import { GUIDES } from "@/lib/guides";
import { cn } from "@/lib/utils";



/** "How to use this page" in three steps. Open by default; remembers if you close it. */
export function PageGuide({ page }: { page: keyof typeof GUIDES }) {
  const [open, setOpen] = useState(true);
  const reduce = useReducedMotion();
  const id = useId();
  const key = `resolveit-guide-${page}`;
  useEffect(() => {
    try {
      if (window.localStorage.getItem(key) === "closed") setOpen(false);
    } catch {
      /* storage unavailable: keep it open */
    }
  }, [key]);
  const toggle = () => {
    setOpen((o) => {
      try {
        window.localStorage.setItem(key, o ? "closed" : "open");
      } catch {
        /* ignore */
      }
      return !o;
    });
  };
  return (
    <section aria-label="How to use this page" className="glass mb-8 rounded-2xl">
      <button type="button" onClick={toggle} aria-expanded={open} aria-controls={id} className="flex min-h-12 w-full items-center gap-3 px-4 text-left">
        <Compass aria-hidden="true" className="size-4 text-signal" />
        <span className="flex-1 text-sm font-semibold">How to use this page</span>
        <ChevronDown aria-hidden="true" className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.ol
            id={id}
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="grid gap-3 overflow-hidden px-4 pb-4 sm:grid-cols-3"
          >
            {GUIDES[page].map((step, i) => (
              <li key={step} className="flex items-start gap-3 rounded-xl border bg-card/70 p-3">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-foreground font-mono text-[11px] font-bold text-background">{i + 1}</span>
                <span className="text-sm leading-snug">{step}</span>
              </li>
            ))}
          </motion.ol>
        ) : null}
      </AnimatePresence>
    </section>
  );
}
