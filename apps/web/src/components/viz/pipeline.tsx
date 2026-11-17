"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Brain, FileText, ShieldCheck, Scale, UserRoundCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

export const STAGES = [
  {
    name: "Raw evidence",
    short: "Read",
    Icon: FileText,
    title: "Keep the original meaning",
    detail:
      "Deterministic rules read the report first. Error codes are protected from masking, and every piece of evidence points back to the exact characters the person typed.",
  },
  {
    name: "PII shield",
    short: "Mask",
    Icon: ShieldCheck,
    title: "Minimize what the model sees",
    detail:
      "Emails, phone numbers, Aadhaar, PAN and other identifiers are masked before any model runs. The original report is encrypted and stored separately.",
  },
  {
    name: "Model bundle",
    short: "Model",
    Icon: Brain,
    title: "Version the whole decision",
    detail:
      "One signed bundle pins the INT8 model, tokenizer, team order, temperature, thresholds and costs. Change any part and it is a new bundle with a new ID.",
  },
  {
    name: "Risk gate",
    short: "Decide",
    Icon: Scale,
    title: "Know when to stop",
    detail:
      "A ticket is routed only when the calibrated risk certificate holds. Too many plausible teams, conflicting details or a security signal stop it and hand it to a person.",
  },
  {
    name: "Human / agent",
    short: "Handoff",
    Icon: UserRoundCheck,
    title: "A considered handoff",
    detail:
      "At most one optional question, or a person decides. AI agents must quote the user's own words to answer, through signed request state.",
  },
] as const;

/** Animated five-stage track. `active` highlights a stage; `running` sends packets along the rail. */
export function PipelineTrack({ active = -1, running = false, className }: { active?: number; running?: boolean; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <ol className={cn("relative grid grid-cols-5 gap-1 sm:gap-2", className)} aria-label="Decision pipeline">
      <svg aria-hidden="true" className="pointer-events-none absolute inset-x-[10%] top-5 h-2 w-[80%] overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 2">
        <line x1="0" y1="1" x2="100" y2="1" stroke="var(--border)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
        <line x1="0" y1="1" x2="100" y2="1" stroke="var(--signal)" strokeWidth="2" vectorEffect="non-scaling-stroke" className={running && !reduce ? "flow-dash" : undefined} opacity={running ? 0.9 : 0} />
      </svg>
      {STAGES.map((stage, i) => {
        const on = i <= active;
        const Icon = stage.Icon;
        return (
          <li key={stage.name} className="relative flex flex-col items-center gap-2 text-center">
            <motion.span
              className={cn(
                "relative z-10 grid size-10 place-items-center rounded-xl border bg-card transition-colors",
                on ? "border-transparent bg-primary text-primary-foreground shadow-[0_0_24px_-4px_var(--glow)]" : "text-muted-foreground",
              )}
              animate={i === active && running && !reduce ? { scale: [1, 1.12, 1] } : { scale: 1 }}
              transition={{ duration: 0.6 }}
            >
              <Icon aria-hidden="true" className="size-[18px]" />
            </motion.span>
            <span className={cn("text-[11px] font-semibold leading-tight sm:text-xs", on ? "text-foreground" : "text-muted-foreground")}>
              {stage.short}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** While a ticket is in flight, step through the stages so waiting has a shape. */
export function PipelineProgress() {
  const [step, setStep] = useState(0);
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => (s < STAGES.length - 1 ? s + 1 : s)), 450);
    const w = setTimeout(() => setSlow(true), 4500);
    return () => {
      clearInterval(t);
      clearTimeout(w);
    };
  }, []);
  return (
    <div className="glass rounded-2xl p-6" role="status" aria-live="polite">
      <p className="eyebrow">Processing</p>
      <p className="mb-6 text-lg font-semibold tracking-tight">{STAGES[step]!.title}…</p>
      <PipelineTrack active={step} running />
      <AnimatePresence>
        {slow ? (
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 text-sm text-muted-foreground">
            The engine sleeps when idle on the free tier. The first request can take up to 30 seconds; your text is safe.
          </motion.p>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
