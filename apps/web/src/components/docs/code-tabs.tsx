"use client";

import { Check, Copy } from "lucide-react";
import { motion } from "motion/react";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/** Tabbed code samples with copy. Tabs follow the WAI-ARIA tabs pattern. */
export function CodeTabs({ samples, className }: { samples: { label: string; code: string }[]; className?: string }) {
  const [active, setActive] = useState(0);
  const [copied, setCopied] = useState(false);
  const reduce = useReducedMotion();
  const id = useId();
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const go = (next: number) => {
    setActive(next);
    tabs.current[next]?.focus();
  };
  const current = samples[active]!;
  return (
    <div className={cn("overflow-hidden rounded-2xl border bg-[#0c0c0e] text-[#e7e5e4]", className)}>
      <div className="flex flex-wrap items-center justify-between gap-x-2 border-b border-white/10 px-2">
        <div role="tablist" aria-label="Language" className="flex min-w-0 overflow-x-auto">
          {samples.map((s, i) => (
            <button
              key={s.label}
              id={`${id}-tab-${i}`}
              ref={(el) => {
                tabs.current[i] = el;
              }}
              role="tab"
              type="button"
              aria-selected={i === active}
              aria-controls={`${id}-panel`}
              tabIndex={i === active ? 0 : -1}
              onClick={() => setActive(i)}
              onKeyDown={(e) => {
                const keys: Record<string, number> = { ArrowRight: (i + 1) % samples.length, ArrowLeft: (i - 1 + samples.length) % samples.length, Home: 0, End: samples.length - 1 };
                if (e.key in keys) {
                  e.preventDefault();
                  go(keys[e.key]!);
                }
              }}
              className={cn("relative min-h-11 px-3 font-mono text-xs", i === active ? "text-white" : "text-[#a8a29e] hover:text-white")}
            >
              {s.label}
              {i === active ? <motion.span layoutId={`${id}-u`} className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-[#ff5a4f]" transition={reduce ? { duration: 0 } : undefined} /> : null}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => void navigator.clipboard?.writeText(current.code).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2 text-xs text-[#a8a29e] hover:text-white"
          aria-label={copied ? "Copied" : `Copy ${current.label} sample`}
        >
          {copied ? <Check aria-hidden="true" className="size-3.5" /> : <Copy aria-hidden="true" className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${active}`} tabIndex={0} className="overflow-x-auto p-4 font-mono text-[12.5px] leading-6">
        {current.code}
      </pre>
    </div>
  );
}
