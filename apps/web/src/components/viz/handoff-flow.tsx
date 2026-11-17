"use client";

import { motion, useReducedMotion } from "motion/react";

export interface Transition {
  from: string;
  to: string;
  count: number;
}

/** Transitions between queues from a list of journeys. Consecutive identical queues never count. */
export function transitionsFromJourneys(journeys: string[][]): Transition[] {
  const counts = new Map<string, Transition>();
  for (const queues of journeys) {
    for (let i = 1; i < queues.length; i++) {
      const from = queues[i - 1]!;
      const to = queues[i]!;
      const key = `${from}\u0000${to}`;
      const t = counts.get(key) ?? { from, to, count: 0 };
      t.count += 1;
      counts.set(key, t);
    }
  }
  return [...counts.values()].sort((a, b) => b.count - a.count);
}

/** Parse API keys such as "Service Desk -> Network" or "A→B". */
export function transitionsFromMap(map: Record<string, number>): Transition[] {
  return Object.entries(map)
    .map(([key, count]) => {
      const [from = key, to = ""] = key.split(/\s*(?:->|→|>)\s*/);
      return { from, to, count };
    })
    .sort((a, b) => b.count - a.count);
}

/** Sankey-style two-column flow: where tickets were, and where they were handed to next. */
export function HandoffFlow({ transitions, title }: { transitions: Transition[]; title: string }) {
  const reduce = useReducedMotion();
  const top = transitions.slice(0, 10);
  if (top.length === 0) {
    return <p className="text-sm text-muted-foreground">No handoffs in this data: every ticket stayed in its first queue.</p>;
  }
  const froms = [...new Set(top.map((t) => t.from))];
  const tos = [...new Set(top.map((t) => t.to))];
  const rows = Math.max(froms.length, tos.length);
  const W = 640;
  const H = Math.max(160, rows * 52 + 24);
  const max = Math.max(...top.map((t) => t.count));
  const y = (i: number, n: number) => 12 + ((H - 24) * (i + 0.5)) / n;
  const x1 = 170;
  const x2 = W - 170;
  return (
    <figure className="min-w-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={title}>
        {top.map((t, i) => {
          const ya = y(froms.indexOf(t.from), froms.length);
          const yb = y(tos.indexOf(t.to), tos.length);
          const mid = (x1 + x2) / 2;
          return (
            <motion.path
              key={`${t.from}-${t.to}`}
              d={`M${x1} ${ya} C${mid} ${ya} ${mid} ${yb} ${x2} ${yb}`}
              fill="none"
              stroke={i === 0 ? "var(--signal)" : "var(--foreground)"}
              strokeOpacity={i === 0 ? 0.75 : 0.18}
              strokeWidth={4 + (t.count / max) * 22}
              strokeLinecap="round"
              initial={reduce ? false : { pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.9, delay: i * 0.06, ease: [0.22, 1, 0.36, 1] }}
            />
          );
        })}
        {froms.map((q, i) => (
          <g key={`f-${q}`}>
            <rect x={x1 - 6} y={y(i, froms.length) - 16} width={6} height={32} rx={3} fill="var(--signal)" />
            <text x={x1 - 14} y={y(i, froms.length)} dy="0.35em" textAnchor="end" fontSize="13" fontWeight="600" fill="var(--foreground)">
              {q.length > 20 ? `${q.slice(0, 19)}…` : q}
            </text>
          </g>
        ))}
        {tos.map((q, i) => (
          <g key={`t-${q}`}>
            <rect x={x2} y={y(i, tos.length) - 16} width={6} height={32} rx={3} fill="var(--foreground)" />
            <text x={x2 + 14} y={y(i, tos.length)} dy="0.35em" fontSize="13" fontWeight="600" fill="var(--foreground)">
              {q.length > 20 ? `${q.slice(0, 19)}…` : q}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>Left: queue a ticket left. Right: queue it went to. Thicker band = more handoffs.</span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="h-1.5 w-4 rounded-full bg-signal" /> busiest handoff
        </span>
      </figcaption>
      <ul className="sr-only">
        {top.map((t) => (
          <li key={`${t.from}-${t.to}`}>
            {t.from} to {t.to}: {t.count}
          </li>
        ))}
      </ul>
    </figure>
  );
}
