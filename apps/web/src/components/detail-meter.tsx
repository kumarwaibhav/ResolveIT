"use client";

import { Check, Minus } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

import { RingGauge } from "@/components/motion";
import { SLOT_LABEL, type MeterResult } from "@/lib/meter";
import { cn } from "@/lib/utils";

/** Counts what the rule patterns can see in the text. Runs in the browser; nothing is sent while typing. */
export function DetailMeter({ result }: { result: MeterResult }) {
  const reduce = useReducedMotion();
  const total = result.found.length + result.missing.length;
  const found = new Set(result.found);
  const order = [...result.found, ...result.missing];
  return (
    <section aria-labelledby="meter-heading" className="rounded-2xl border bg-card/70 p-4">
      <div className="flex items-center gap-4">
        <RingGauge value={total ? result.found.length / total : 0} size={64} stroke={6}>
          <span aria-hidden="true" className="text-sm font-bold tabular">{result.found.length}</span>
        </RingGauge>
        <div className="min-w-0 flex-1">
          <h2 id="meter-heading" className="text-sm font-semibold">Details spotted so far</h2>
          <p className="font-mono text-sm tabular text-muted-foreground" aria-live="polite">
            {result.found.length} of {total}
          </p>
          <div
            role="meter"
            aria-labelledby="meter-heading"
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={result.found.length}
            aria-valuetext={`${result.found.length} of ${total} details`}
            className="mt-2 flex gap-1"
          >
            {order.map((slot) => (
              <span key={slot} className={cn("h-1.5 flex-1 rounded-full transition-colors duration-300", found.has(slot) ? "bg-primary" : "bg-muted")} />
            ))}
          </div>
        </div>
      </div>
      <ul className="mt-4 flex flex-wrap gap-1.5 text-xs">
        {order.map((slot) => {
          const on = found.has(slot);
          return (
            <motion.li
              key={slot}
              layout={!reduce}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 font-medium",
                on ? "border-ok/30 bg-ok-surface text-ok" : "border-dashed text-muted-foreground",
              )}
            >
              {on ? <Check aria-hidden="true" className="size-3" /> : <Minus aria-hidden="true" className="size-3" />}
              {SLOT_LABEL[slot] ?? slot}
              <span className="sr-only">{on ? ", found" : ", not yet stated"}</span>
            </motion.li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs text-muted-foreground">Checked on this device as you type. Missing details never block sending.</p>
    </section>
  );
}
