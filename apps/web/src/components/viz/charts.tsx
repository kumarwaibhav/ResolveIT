"use client";

import { motion } from "motion/react";
import { useReducedMotion } from "@/lib/use-reduced-motion";

import { cn } from "@/lib/utils";

export interface Segment {
  label: string;
  value: number;
  note?: string;
}

const SHADES = ["var(--signal)", "var(--foreground)", "color-mix(in srgb, var(--signal) 55%, var(--card))", "color-mix(in srgb, var(--foreground) 55%, var(--card))", "color-mix(in srgb, var(--signal) 30%, var(--card))", "color-mix(in srgb, var(--foreground) 30%, var(--card))", "var(--muted-foreground)"];

/** One horizontal bar split into labelled segments, with a legend that carries every number. */
export function StackedBar({ segments, caption, compact = false }: { segments: Segment[]; caption: string; compact?: boolean }) {
  const reduce = useReducedMotion();
  const total = segments.reduce((s, x) => s + x.value, 0);
  return (
    <figure>
      <div className="flex h-5 w-full overflow-hidden rounded-full bg-muted" aria-hidden="true">
        {segments.map((s, i) => (
          <motion.span
            key={s.label}
            className="h-full first:rounded-l-full last:rounded-r-full"
            style={{ background: SHADES[i % SHADES.length] }}
            initial={reduce ? false : { width: 0 }}
            animate={{ width: `${(s.value / total) * 100}%` }}
            transition={{ duration: 0.8, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] }}
          />
        ))}
      </div>
      <figcaption className="sr-only">{caption}</figcaption>
      <ul className={cn("mt-5 grid gap-x-6 gap-y-3", compact ? "" : "sm:grid-cols-2 lg:grid-cols-3")}>
        {segments.map((s, i) => (
          <li key={s.label} className="flex items-start gap-3">
            <span aria-hidden="true" className="mt-1 size-3 shrink-0 rounded-sm" style={{ background: SHADES[i % SHADES.length] }} />
            <span className="min-w-0 text-sm">
              <span className="font-semibold">{s.label}</span>{" "}
              <span className="font-mono text-muted-foreground tabular">
                {s.value.toLocaleString("en-IN")} · {((s.value / total) * 100).toFixed(1)}%
              </span>
              {s.note ? <span className="block text-xs text-muted-foreground">{s.note}</span> : null}
            </span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** Donut of outcome shares. The centre and legend carry the numbers; the ring is decorative. */
export function Donut({ segments, centre, sub, className }: { segments: Segment[]; centre: string; sub: string; className?: string }) {
  const reduce = useReducedMotion();
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = 70;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className={cn("flex flex-col items-center gap-6 sm:flex-row", className)}>
      <div className="relative size-48 shrink-0">
        <svg viewBox="0 0 180 180" className="size-48 -rotate-90" aria-hidden="true">
          <circle cx="90" cy="90" r={r} fill="none" stroke="var(--muted)" strokeWidth="20" />
          {segments.map((s, i) => {
            const len = (s.value / total) * c;
            const el = (
              <motion.circle
                key={s.label}
                cx="90"
                cy="90"
                r={r}
                fill="none"
                stroke={SHADES[i % SHADES.length]}
                strokeWidth="20"
                strokeDasharray={`${len} ${c - len}`}
                strokeDashoffset={-offset}
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: i * 0.12 }}
              />
            );
            offset += len;
            return el;
          })}
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          <div>
            <span className="block text-3xl font-bold tracking-[-0.04em] tabular">{centre}</span>
            <span className="block text-xs text-muted-foreground">{sub}</span>
          </div>
        </div>
      </div>
      <ul className="w-full space-y-3">
        {segments.map((s, i) => (
          <li key={s.label} className="flex items-start gap-3 text-sm">
            <span aria-hidden="true" className="mt-1 size-3 shrink-0 rounded-sm" style={{ background: SHADES[i % SHADES.length] }} />
            <span>
              <span className="font-semibold">{s.label}</span>{" "}
              <span className="font-mono text-muted-foreground tabular">{s.value.toLocaleString("en-IN")}</span>
              {s.note ? <span className="block text-xs text-muted-foreground">{s.note}</span> : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
