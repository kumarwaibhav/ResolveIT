import { useId } from "react";

import { cn } from "@/lib/utils";

/** The Monolith: two uncertain inputs meet one calibration node; one crimson rail exits right. */
const TILE =
  "M24 0C38.4 0 43.2 0 45.6 2.4C48 4.8 48 9.6 48 24C48 38.4 48 43.2 45.6 45.6C43.2 48 38.4 48 24 48C9.6 48 4.8 48 2.4 45.6C0 43.2 0 38.4 0 24C0 9.6 0 4.8 2.4 2.4C4.8 0 9.6 0 24 0Z";
const GEO = {
  normal: { ch: 5, y1: 13, y2: 35, cut: 7.5, node: 5, rail: 5, railCut: 9 },
  small: { ch: 6.5, y1: 12, y2: 36, cut: 8.75, node: 6, rail: 6.5, railCut: 11 },
};
const NX = 21;
const inputs = (y1: number, y2: number) =>
  `M-2 ${y1}H0C10.5 ${y1} 10.5 24 ${NX} 24M-2 ${y2}H0C10.5 ${y2} 10.5 24 ${NX} 24`;

interface MarkProps {
  size?: number;
  className?: string;
  title?: string;
  animate?: boolean;
}

/** Tile follows the text colour (ink on light, alabaster on dark); the rail is always the signal. */
export function MonolithMark({ size = 32, className, title, animate = false }: MarkProps) {
  const id = `m${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const g = size <= 32 ? GEO.small : GEO.normal;
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      className={cn("shrink-0", animate && "monolith-animate", className)}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      <defs>
        <mask id={`${id}-m`} maskUnits="userSpaceOnUse" x="-4" y="-4" width="56" height="56">
          <rect x="-4" y="-4" width="56" height="56" fill="#fff" />
          <path className="mi" d={inputs(g.y1, g.y2)} fill="none" stroke="#000" strokeWidth={g.ch} />
          <circle className="mn" cx={NX} cy="24" r={g.cut} fill="#000" />
          <rect className="mr" x={NX} y={24 - g.railCut / 2} width={52 - NX} height={g.railCut} fill="#000" />
        </mask>
        <clipPath id={`${id}-c`}>
          <path d={TILE} />
        </clipPath>
      </defs>
      <path d={TILE} fill="currentColor" mask={`url(#${id}-m)`} />
      <g clipPath={`url(#${id}-c)`} fill="var(--signal)">
        <circle className="mn" cx={NX} cy="24" r={g.node} />
        <rect className="mr" x={NX} y={24 - g.rail / 2} width={48 - NX} height={g.rail} />
      </g>
    </svg>
  );
}

/** Mark + "ResolveIT" wordmark. "Resolve" 600, "IT" 800, so crimson is spent once, on the rail. */
export function Wordmark({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <MonolithMark size={size} />
      <span className="text-[1.15rem] leading-none tracking-[-0.035em]">
        <span className="font-semibold">Resolve</span>
        <span className="font-extrabold">IT</span>
      </span>
    </span>
  );
}
