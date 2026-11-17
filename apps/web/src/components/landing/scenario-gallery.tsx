"use client";

import { ArrowRight, CircleHelp, Mail, MessageSquare, Phone, Route, ShieldAlert, Smartphone, UserRound } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import Link from "next/link";
import { useMemo, useState } from "react";

import { SLOT_LABEL } from "@/lib/meter";
import { KIND_LABEL, SCENARIOS, type Scenario, type ScenarioKind } from "@/lib/scenarios";
import { cn } from "@/lib/utils";

export interface Observed {
  state: string;
  routed_team: string | null;
  recommended_team: string | null;
  defer_reason: string | null;
  question: string | null;
  security_trigger: boolean;
  top_team: string | null;
  top_p: number | null;
  found: string[];
  round_trip_ms: number;
}

const team = (t: string | null | undefined) => (t ?? "").replaceAll("_", " ");
const REASON: Record<string, string> = {
  security_escalation: "security escalation",
  set_too_large: "too many teams plausible",
  no_conforming_team: "no team fits well",
  risk_above_defer_cost: "routing too risky",
  critical_contradiction: "details conflict",
  shadow_mode: "shadow mode",
  unmapped_queue: "queue not mapped",
};
const CHANNEL_ICON = { Slack: MessageSquare, "Teams chat": MessageSquare, Email: Mail, Portal: MessageSquare, "Phone transcript": Phone, WhatsApp: Smartphone } as const;

function Outcome({ o }: { o: Observed | undefined }) {
  if (!o) return <p className="text-xs text-muted-foreground">Not yet run against the live engine.</p>;
  const view =
    o.state === "ROUTED"
      ? { Icon: Route, label: `Routed to ${team(o.routed_team)}`, cls: "bg-primary text-primary-foreground" }
      : o.state === "PENDING_CLARIFICATION"
        ? { Icon: CircleHelp, label: `Asked: ${o.question ?? "one question"}`, cls: "bg-info-surface text-info" }
        : o.security_trigger
          ? { Icon: ShieldAlert, label: "To a person · Security flagged", cls: "bg-risk-surface text-risk" }
          : { Icon: UserRound, label: `To a person · ${REASON[o.defer_reason ?? ""] ?? "needs judgment"}`, cls: "bg-warn-surface text-warn" };
  return (
    <div className="space-y-2">
      <p className={cn("inline-flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-semibold", view.cls)}>
        <view.Icon aria-hidden="true" className="size-4 shrink-0" />
        {view.label}
      </p>
      <p className="text-xs text-muted-foreground">
        {o.found.length > 0 ? `Read: ${o.found.map((s) => SLOT_LABEL[s] ?? s).join(", ")}` : "No details read"}
        {o.top_team && o.top_p !== null ? ` · top guess ${team(o.top_team)} ${(o.top_p * 100).toFixed(0)}%` : ""}
      </p>
    </div>
  );
}

function Card({ s, o }: { s: Scenario; o: Observed | undefined }) {
  const Icon = CHANNEL_ICON[s.channel];
  return (
    <article className="glass flex h-full flex-col rounded-3xl p-6">
      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Icon aria-hidden="true" className="size-4" /> {s.channel} · {s.who}
        </span>
        <span className="rounded-full border px-2.5 py-0.5 font-mono text-xs uppercase tracking-wider text-muted-foreground">{KIND_LABEL[s.kind].label}</span>
      </div>
      <h3 className="mt-4 text-lg font-bold tracking-[-0.02em]">{s.title}</h3>
      <blockquote lang={s.locale === "hi" ? "hi" : undefined} className="mt-3 rounded-2xl rounded-tl-sm border bg-card px-4 py-3 text-[15px] leading-relaxed">
        {s.text}
      </blockquote>
      <p className="mt-3 text-sm text-muted-foreground">{s.why}</p>
      <div className="mt-auto pt-5">
        <p className="mono-label mb-2">What the engine did</p>
        <Outcome o={o} />
        <Link href={`/intake?sample=${s.id}`} className="mt-4 inline-flex min-h-10 items-center gap-1.5 text-sm font-semibold text-signal">
          Try it yourself <ArrowRight aria-hidden="true" className="size-4" />
          <span className="sr-only">: {s.title}</span>
        </Link>
      </div>
    </article>
  );
}

export function ScenarioGallery({ observed, verifiedAt }: { observed: Record<string, Observed>; verifiedAt: string | null }) {
  const [kind, setKind] = useState<ScenarioKind | "all">("all");
  const reduce = useReducedMotion();
  const list = useMemo(() => (kind === "all" ? SCENARIOS : SCENARIOS.filter((s) => s.kind === kind)), [kind]);
  const kinds = Object.keys(KIND_LABEL) as ScenarioKind[];
  return (
    <div>
      <div role="group" aria-label="Filter examples" className="flex flex-wrap justify-center gap-2">
        {(["all", ...kinds] as const).map((k) => {
          const on = kind === k;
          const count = k === "all" ? SCENARIOS.length : SCENARIOS.filter((s) => s.kind === k).length;
          return (
            <button
              key={k}
              type="button"
              aria-pressed={on}
              onClick={() => setKind(k)}
              className={cn("relative min-h-10 rounded-full px-4 text-sm font-semibold transition-colors", on ? "text-background" : "glass text-muted-foreground hover:text-foreground")}
            >
              {on ? <motion.span layoutId="kind-pill" className="absolute inset-0 rounded-full bg-foreground" transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 400, damping: 34 }} /> : null}
              <span className="relative">
                {k === "all" ? "All" : KIND_LABEL[k].label} <span className="font-mono text-xs">{count}</span>
              </span>
            </button>
          );
        })}
      </div>
      <p className="mt-4 text-center text-sm text-muted-foreground" aria-live="polite">
        {kind === "all" ? "Every kind of ticket a service desk sees." : KIND_LABEL[kind].blurb}
      </p>
      <h2 className="sr-only">Example tickets</h2>
      <motion.ul layout={!reduce} className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <AnimatePresence mode="popLayout" initial={false}>
          {list.map((s) => (
            <motion.li
              key={s.id}
              layout={!reduce}
              initial={reduce ? false : { opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={reduce ? { opacity: 1 } : { opacity: 0, scale: 0.97 }}
              transition={{ duration: 0.25 }}
            >
              <Card s={s} o={observed[s.id]} />
            </motion.li>
          ))}
        </AnimatePresence>
      </motion.ul>
      <p className="mt-8 text-center text-xs text-muted-foreground">
        {verifiedAt ? `Outcomes recorded from the live demo engine on ${verifiedAt.slice(0, 10)}, synthetic demo bundle.` : "Outcomes will appear once recorded from the live engine."}
      </p>
    </div>
  );
}
