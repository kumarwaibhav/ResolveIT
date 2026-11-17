"use client";

import { ArrowRight, Check, Minus, ShieldAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { RingGauge } from "@/components/motion";
import { measure, SLOT_LABEL } from "@/lib/meter";
import { cn } from "@/lib/utils";

/** One calm, debounced announcement instead of a live region over the whole column. */
function SandboxStatus({ found, total, security }: { found: number; total: number; security: boolean }) {
  const [msg, setMsg] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setMsg(`${found} of ${total} details found.${security ? " Security signal: this goes straight to a person." : ""}`), 600);
    return () => clearTimeout(t);
  }, [found, total, security]);
  return (
    <p className="sr-only" role="status">
      {msg}
    </p>
  );
}

const SAMPLES = [
  { label: "Clear", text: "Outlook keeps crashing for the whole floor since this morning, urgent" },
  { label: "Vague", text: "kal se kuch bhi kaam nahi kar raha, please jaldi dekho" },
  { label: "Security", text: "I clicked a link in an email and typed my password" },
];

/** Runs entirely in the browser: the same rule patterns the engine uses, no network. */
export function TrySandbox() {
  const [text, setText] = useState(SAMPLES[0]!.text);
  const result = useMemo(() => measure(text), [text]);
  const reduce = useReducedMotion();
  const total = result.found.length + result.missing.length;
  const found = new Set(result.found);
  return (
    <div className="glass-strong grid overflow-hidden rounded-[28px] lg:grid-cols-[1.15fr_1fr]">
      <div className="border-b p-6 sm:p-8 lg:border-b-0 lg:border-r">
        <label htmlFor="try-text" className="mono-label">Type like a user would</label>
        <textarea
          id="try-text"
          value={text}
          rows={4}
          maxLength={500}
          onChange={(e) => setText(e.target.value)}
          className="mt-3 block w-full resize-none rounded-2xl border bg-card px-4 py-3 text-lg leading-relaxed outline-none transition-shadow focus:border-ring focus:shadow-[0_0_0_4px_var(--glow)]"
        />
        <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Sample reports">
          {SAMPLES.map((s) => (
            <button
              key={s.label}
              type="button"
              aria-pressed={text === s.text}
              onClick={() => setText(s.text)}
              className="min-h-10 rounded-full border bg-card px-4 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground aria-pressed:border-signal/50 aria-pressed:text-foreground"
            >
              {s.label}
            </button>
          ))}
        </div>
        <p className="mt-5 text-xs text-muted-foreground">This preview runs on your device; nothing is sent. The full decision runs in a signed-in workspace.</p>
      </div>
      <div className="p-6 sm:p-8">
        <SandboxStatus found={result.found.length} total={total} security={result.security} />
        <div className="flex items-center gap-5">
          <RingGauge value={total ? result.found.length / total : 0} size={92} stroke={8}>
            <span className="text-xl font-bold tabular">{result.found.length}<span className="text-sm text-muted-foreground">/{total}</span></span>
          </RingGauge>
          <div>
            <p className="text-lg font-bold tracking-[-0.02em]">Details found</p>
            <p className="text-sm text-muted-foreground">The more it can read, the fewer questions it asks.</p>
          </div>
        </div>
        <ul className="mt-6 grid grid-cols-2 gap-2">
          {[...result.found, ...result.missing].map((slot) => {
            const on = found.has(slot);
            return (
              <motion.li
                key={slot}
                layout={!reduce}
                className={cn("flex items-center gap-2 rounded-xl border px-3 py-2 text-sm", on ? "border-ok/30 bg-ok-surface text-ok" : "border-dashed text-muted-foreground")}
              >
                {on ? <Check aria-hidden="true" className="size-4" /> : <Minus aria-hidden="true" className="size-4" />}
                {SLOT_LABEL[slot] ?? slot}
                <span className="sr-only">{on ? ": found" : ": not stated"}</span>
              </motion.li>
            );
          })}
        </ul>
        <AnimatePresence>
          {result.security ? (
            <motion.p
              initial={reduce ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-4 flex items-center gap-2 rounded-xl border border-risk/30 bg-risk-surface px-3 py-2 text-sm font-medium text-risk"
            >
              <ShieldAlert aria-hidden="true" className="size-4 shrink-0" /> Security signal: this skips every question and goes straight to a person.
            </motion.p>
          ) : null}
        </AnimatePresence>
        <Link href="/intake" className="workspace-button primary mt-6 !rounded-xl">
          Get the full decision <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
      </div>
    </div>
  );
}
