"use client";

import { animate, motion, useInView, useMotionValue, useReducedMotion, useSpring, useTransform } from "motion/react";
import { type ComponentProps, type ReactNode, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

const EASE = [0.22, 1, 0.36, 1] as const;

/** Short fade-up on mount. Under reduced motion it renders in place with no transition. */
export function Reveal({
  children,
  delay = 0,
  className,
  as = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "li";
}) {
  const reduce = useReducedMotion();
  const Comp = motion[as];
  return (
    <Comp
      className={className}
      initial={reduce ? false : { opacity: 0, y: 10, filter: "blur(4px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.32, delay: Math.min(delay, 0.12), ease: EASE }}
    >
      {children}
    </Comp>
  );
}

/** Glass card with a cursor-following crimson spotlight and an optional gentle 3D tilt. */
export function GlassCard({
  children,
  className,
  tilt = false,
  ...rest
}: { children: ReactNode; className?: string; tilt?: boolean } & Omit<ComponentProps<"div">, "children">) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const rx = useSpring(useMotionValue(0), { stiffness: 220, damping: 22 });
  const ry = useSpring(useMotionValue(0), { stiffness: 220, damping: 22 });
  const enableTilt = tilt && !reduce;
  return (
    <motion.div
      ref={ref}
      {...(rest as ComponentProps<typeof motion.div>)}
      style={enableTilt ? { rotateX: rx, rotateY: ry, transformPerspective: 1200 } : undefined}
      onMouseMove={(e) => {
        const el = ref.current;
        if (!el) return;
        const r = el.getBoundingClientRect();
        const x = e.clientX - r.left;
        const y = e.clientY - r.top;
        el.style.setProperty("--mx", `${x}px`);
        el.style.setProperty("--my", `${y}px`);
        if (enableTilt) {
          ry.set(((x / r.width) - 0.5) * 6);
          rx.set(-((y / r.height) - 0.5) * 6);
        }
      }}
      onMouseLeave={() => {
        rx.set(0);
        ry.set(0);
      }}
      className={cn("glass spotlight rounded-2xl", className)}
    >
      {children}
    </motion.div>
  );
}

/** Counts up to a measured value once visible. The final value is always what screen readers get. */
export function NumberTicker({ value, decimals = 0, suffix = "", className }: { value: number; decimals?: number; suffix?: string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : 0);
  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      setShown(value);
      return;
    }
    const controls = animate(0, value, { duration: 1.1, ease: EASE, onUpdate: setShown });
    return () => controls.stop();
  }, [inView, reduce, value]);
  const fmt = (n: number) => n.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return (
    <span ref={ref} className={cn("tabular", className)}>
      <span aria-hidden="true">{fmt(shown)}{suffix}</span>
      <span className="sr-only">{fmt(value)}{suffix}</span>
    </span>
  );
}

/** Animated bar that grows from zero to a fraction (0–1). Decorative: pair it with a text value. */
export function GrowBar({ value, className, barClassName, delay = 0 }: { value: number; className?: string; barClassName?: string; delay?: number }) {
  const reduce = useReducedMotion();
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div aria-hidden="true" className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}>
      <motion.div
        className={cn("h-full rounded-full bg-primary", barClassName)}
        initial={reduce ? false : { width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.7, delay, ease: EASE }}
      />
    </div>
  );
}

/** Radial gauge. `value` is 0–1. Decorative ring; the caller prints the number. */
export function RingGauge({ value, size = 120, stroke = 10, className, children }: { value: number; size?: number; stroke?: number; className?: string; children?: ReactNode }) {
  const reduce = useReducedMotion();
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const progress = useMotionValue(reduce ? value : 0);
  const offset = useTransform(progress, (p) => c * (1 - Math.max(0, Math.min(1, p))));
  useEffect(() => {
    if (reduce) {
      progress.set(value);
      return;
    }
    const controls = animate(progress, value, { duration: 0.9, ease: EASE });
    return () => controls.stop();
  }, [progress, reduce, value]);
  return (
    <div className={cn("relative grid place-items-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--muted)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--signal)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          style={{ strokeDashoffset: offset }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}
