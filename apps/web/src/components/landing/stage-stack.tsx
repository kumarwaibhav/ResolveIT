"use client";

import { motion, useReducedMotion } from "motion/react";

import { STAGES } from "@/components/viz/pipeline";
import { cn } from "@/lib/utils";

/** Five isometric plates, one per pipeline stage. The active plate lifts and lights up. */
export function StageStack({ active }: { active: number }) {
  const reduce = useReducedMotion();
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[420px] [perspective:1400px]" aria-hidden="true">
      <div className="absolute inset-0 [transform-style:preserve-3d] [transform:rotateX(58deg)_rotateZ(-42deg)]">
        {STAGES.map((stage, i) => {
          const on = i === active;
          const done = i < active;
          const z = (STAGES.length - 1 - i) * 46;
          const Icon = stage.Icon;
          return (
            <motion.div
              key={stage.name}
              className={cn(
                "absolute inset-[16%] grid place-items-center rounded-[28px] border",
                on ? "border-signal/70 bg-[color-mix(in_srgb,var(--card)_70%,var(--signal)_30%)]" : done ? "border-signal/30 bg-card/80" : "bg-card/60",
              )}
              style={{ boxShadow: on ? "0 0 60px -6px var(--glow), inset 0 1px 0 rgb(255 255 255 / .15)" : "0 18px 40px -20px rgb(0 0 0 / .35)" }}
              initial={false}
              animate={{ z: on ? z + 34 : z, opacity: on || done ? 1 : 0.55 }}
              transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 160, damping: 22 }}
            >
              <span className={cn("grid size-14 place-items-center rounded-2xl [transform:rotateZ(42deg)]", on ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>
                <Icon className="size-7" />
              </span>
              <span className="pointer-events-none absolute left-4 top-3 font-mono text-[11px] text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
            </motion.div>
          );
        })}
        <div className="absolute inset-[16%] translate-z-[-30px] rounded-[28px] border border-dashed opacity-40" />
      </div>
    </div>
  );
}
