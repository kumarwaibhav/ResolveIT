"use client";

import { ArrowRight, Bot, Check, CheckCircle2, CircleDashed, Cpu, FileCode2, KeyRound, Lock, Repeat2, ShieldCheck, UserRound } from "lucide-react";
import { AnimatePresence, motion, useInView } from "motion/react";
import Link from "next/link";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { MonolithMark } from "@/components/brand/monolith";
import { GrowBar, NumberTicker } from "@/components/motion";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ Proof */

/** 455 cells = 35 × 13. Every auto-routed ticket in the frozen test, each one correct. */
export function ProofCards() {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref, { once: true, amount: 0.3 });
  const reduce = useReducedMotion();
  const on = seen || reduce;
  return (
    <div ref={ref} className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-3xl border bg-card p-6 sm:p-8">
        <p className="mono-label">Auto-routed tickets, frozen test</p>
        <p className="mt-2 text-[clamp(2.5rem,5vw,3.5rem)] font-semibold leading-none tracking-[-0.05em]">
          <NumberTicker value={455} /> <span className="text-muted-foreground">/ 455</span>
        </p>
        <p className="mt-2 text-sm text-muted-foreground">reached the right team. Zero misroutes.</p>
        <div aria-hidden="true" className="mt-6 grid gap-[3px]" style={{ gridTemplateColumns: "repeat(35, minmax(0, 1fr))" }}>
          {Array.from({ length: 455 }, (_, i) => (
            <span
              key={i}
              className={cn("aspect-square rounded-[2px] transition-colors duration-300", on ? "bg-signal" : "bg-muted")}
              style={{ transitionDelay: reduce ? "0ms" : `${(i % 35) * 14 + Math.floor(i / 35) * 22}ms` }}
            />
          ))}
        </div>
        <p className="mt-3 text-[13px] text-muted-foreground">One square per ticket it routed on its own.</p>
      </div>

      <div className="flex flex-col rounded-3xl border bg-card p-6 sm:p-8">
        <p className="mono-label">624 tickets it had never seen</p>
        <p className="mt-2 text-[clamp(2.5rem,5vw,3.5rem)] font-semibold leading-none tracking-[-0.05em]">
          <NumberTicker value={90.7} decimals={1} suffix="%" />
        </p>
        <p className="mt-2 text-sm text-muted-foreground">reached the right team without a person, including after one answer.</p>
        <div className="mt-auto space-y-6 pt-8">
          {[
            { l: "Right team without a person", v: 0.907 },
            { l: "Right team inside the plausible set", v: 0.923 },
          ].map((b, i) => (
            <div key={b.l}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span>{b.l}</span>
                <span className="font-mono tabular">{(b.v * 100).toFixed(1)}%</span>
              </div>
              <div className="relative mt-2">
                <GrowBar value={b.v} delay={i * 0.15} className="h-2.5" />
                <span aria-hidden="true" className="absolute -top-1.5 h-5.5 w-px bg-foreground" style={{ left: "90%" }} />
              </div>
            </div>
          ))}
          <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
            <span aria-hidden="true" className="h-3 w-px bg-foreground" /> Target: 90% inside the plausible set
          </p>
        </div>
      </div>

      <ul className="grid gap-px overflow-hidden rounded-3xl border bg-border sm:grid-cols-3 lg:col-span-2">
        {[
          { v: 40, s: " ms", l: "Median decision", n: "A typical ticket, on a CPU" },
          { v: 315, s: " MB", l: "The whole model", n: "INT8, checked by hash at start-up" },
          { v: 0, s: "", l: "LLMs in the decision", n: "Rules and one calibrated encoder" },
        ].map((x) => (
          <li key={x.l} className="bg-card p-6">
            <p className="text-3xl font-semibold tracking-[-0.04em]">
              <NumberTicker value={x.v} suffix={x.s} />
            </p>
            <p className="mt-1 text-sm font-medium">{x.l}</p>
            <p className="text-[13px] text-muted-foreground">{x.n}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------ Product steps */

const STEPS = [
  { tab: "Report", t: "Report it in plain words", d: "Anyone types the problem as they would say it, in English, Hindi or Hinglish. The details it picked up are shown back, so nothing is hidden." },
  { tab: "Review", t: "Two people label blind", d: "Reviewers label the same tickets without seeing each other's answer or the model's. Where they disagree, a third person settles it." },
  { tab: "Bounce", t: "See where tickets get passed around", d: "Upload a queue history. Tickets that ping-pong between teams are flagged, with the hand-offs that cost the most time." },
  { tab: "Evaluate", t: "Prove it before it routes", d: "Routing on your own tickets unlocks only after the model passes a frozen test on tickets your people reviewed." },
];

function WindowBody({ i }: { i: number }) {
  if (i === 0)
    return (
      <div className="space-y-4">
        <div className="rounded-xl border bg-background/60 p-4 text-sm leading-relaxed">Outlook keeps crashing for the whole floor since this morning</div>
        <div className="flex flex-wrap gap-2">
          {["System or app", "Who is affected", "When it started", "How often"].map((c) => (
            <span key={c} className="inline-flex items-center gap-1.5 rounded-full border border-ok/30 bg-ok-surface px-2.5 py-1 text-xs text-ok">
              <Check aria-hidden="true" className="size-3" /> {c}
            </span>
          ))}
        </div>
        <div className="flex items-center justify-between rounded-xl border border-signal/40 p-4">
          <span>
            <span className="block text-[13px] text-muted-foreground">Sent to</span>
            <span className="text-lg font-semibold">Email & Collaboration</span>
          </span>
          <span className="font-mono text-sm tabular text-muted-foreground">score 0.97</span>
        </div>
      </div>
    );
  if (i === 1)
    return (
      <div className="overflow-hidden rounded-xl border">
        <div className="grid grid-cols-[1.6fr_1fr_1fr_auto] gap-3 border-b bg-muted/50 px-4 py-2 text-[13px] text-muted-foreground">
          <span>Ticket</span>
          <span>Reviewer A</span>
          <span>Reviewer B</span>
          <span className="sr-only">Agreement</span>
        </div>
        {[
          ["VPN drops every few minutes", "Network", "Network", true],
          ["Okta MFA loop", "Identity", "Identity", true],
          ["After the Okta update, SAP won't open", "Identity", "ERP", false],
          ["Printer queue stuck", "Hardware", "Hardware", true],
        ].map(([t, a, b, ok]) => (
          <div key={String(t)} className="grid grid-cols-[1.6fr_1fr_1fr_auto] items-center gap-3 border-b px-4 py-3 text-sm last:border-b-0">
            <span className="truncate">{t}</span>
            <span>{a}</span>
            <span>{b}</span>
            {ok ? (
              <CheckCircle2 aria-label="Agree" className="size-4 text-ok" />
            ) : (
              <span className="rounded-full bg-warn-surface px-2 py-0.5 text-xs font-medium text-warn">Third look</span>
            )}
          </div>
        ))}
      </div>
    );
  if (i === 2)
    return (
      <div className="space-y-3">
        {[
          { path: ["Service desk", "Network", "Identity", "Network"], flag: true },
          { path: ["Service desk", "Database"], flag: false },
          { path: ["Service desk", "Hardware", "Software", "Hardware", "Software"], flag: true },
        ].map((j, k) => (
          <div key={k} className="flex flex-wrap items-center gap-1.5 rounded-xl border p-3 text-xs">
            {j.path.map((q, n) => (
              <span key={n} className="inline-flex items-center gap-1.5">
                {n > 0 ? <ArrowRight aria-hidden="true" className="size-3 text-muted-foreground" /> : null}
                <span className={cn("rounded-md px-2 py-1", n > 0 && j.flag ? "bg-risk-surface text-risk" : "bg-muted")}>{q}</span>
              </span>
            ))}
            {j.flag ? (
              <span className="ml-auto inline-flex items-center gap-1 font-medium text-risk">
                <Repeat2 aria-hidden="true" className="size-3.5" /> Ping-pong
              </span>
            ) : (
              <span className="ml-auto inline-flex items-center gap-1 font-medium text-ok">
                <Check aria-hidden="true" className="size-3.5" /> Direct
              </span>
            )}
          </div>
        ))}
      </div>
    );
  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">Certification</span>
        <span className="rounded-full border px-2.5 py-0.5 text-xs">Shadow mode</span>
      </div>
      <ol className="mt-4 space-y-2">
        {[
          ["Training", "Fine-tuned multilingual encoder", true],
          ["Scaling", "Calibrated on the INT8 outputs", true],
          ["Conformal fit", "Plausible-team sets", true],
          ["Risk certification", "Per queue, on generated tickets", true],
          ["Frozen human test", "Needs your reviewed tickets", false],
        ].map(([n, note, done]) => (
          <li key={String(n)} className={cn("flex items-center gap-3 rounded-xl border p-3 text-sm", !done && "border-dashed")}>
            {done ? <CheckCircle2 aria-hidden="true" className="size-4 text-ok" /> : <CircleDashed aria-hidden="true" className="size-4 text-muted-foreground" />}
            <span className="font-medium">{n}</span>
            <span className="ml-auto text-[13px] text-muted-foreground">{note}</span>
            <span className="sr-only">{done ? "done" : "not yet"}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ProductSteps() {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLLIElement | null)[]>([]);
  const reduce = useReducedMotion();
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(Number((e.target as HTMLElement).dataset.i));
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    refs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, []);
  return (
    <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-14">
      <ol className="order-2 min-w-0 lg:order-1">
        {STEPS.map((s, i) => (
          <li
            key={s.tab}
            ref={(el) => {
              refs.current[i] = el;
            }}
            data-i={i}
            className={cn("group border-l-2 py-5 pl-5 transition-colors duration-500 lg:min-h-[28vh]", i === active ? "border-signal" : "border-border")}
          >
            <p className="flex items-baseline gap-3">
              <span className="font-mono text-xs text-signal">{String(i + 1).padStart(2, "0")}</span>
              <span className={cn("text-xl font-semibold tracking-[-0.02em] transition-colors duration-500", i === active ? "text-foreground" : "text-muted-foreground")}>{s.t}</span>
            </p>
            <p className="mt-2 max-w-md leading-relaxed text-muted-foreground">{s.d}</p>
          </li>
        ))}
      </ol>
      <div className="order-1 min-w-0 lg:order-2">
        <div className="lg:sticky lg:top-28 [perspective:1600px]">
          <div className="overflow-hidden rounded-2xl border bg-card shadow-[0_40px_90px_-30px_rgb(0_0_0/.8),0_0_0_1px_rgb(255_255_255/.04)] lg:[transform:rotateY(-7deg)_rotateX(3deg)]">
            <div className="flex items-center gap-2 border-b px-3 py-2.5">
              <MonolithMark size={20} className="text-foreground" />
              <div className="flex gap-1 overflow-x-auto" role="group" aria-label="Product rooms">
                {STEPS.map((s, i) => (
                  <button
                    key={s.tab}
                    type="button"
                    aria-pressed={i === active}
                    onClick={() => setActive(i)}
                    className="min-h-9 whitespace-nowrap rounded-lg px-3 text-sm text-muted-foreground transition-colors aria-pressed:bg-muted aria-pressed:text-foreground"
                  >
                    {s.tab}
                  </button>
                ))}
              </div>
              <span className="ml-auto hidden font-mono text-[13px] text-muted-foreground sm:inline">demo workspace</span>
            </div>
            <div className="min-h-[340px] p-5 sm:p-6">
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={active}
                  initial={reduce ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduce ? undefined : { opacity: 0, y: -6 }}
                  transition={{ duration: 0.25 }}
                >
                  <WindowBody i={active} />
                </motion.div>
              </AnimatePresence>
            </div>
            <ul className="grid grid-cols-3 border-t text-xs">
              {[
                { Icon: Cpu, t: "Runs on CPU", d: "No GPU in the path" },
                { Icon: KeyRound, t: "Keys stay server-side", d: "Never in the browser" },
                { Icon: FileCode2, t: "Versioned decisions", d: "One signed bundle" },
              ].map(({ Icon, t, d }) => (
                <li key={t} className="border-r p-3 last:border-r-0 sm:p-4">
                  <Icon aria-hidden="true" className="size-4 text-signal" />
                  <p className="mt-2 font-semibold">{t}</p>
                  <p className="text-muted-foreground">{d}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- Review loop */

const LOOP = [
  { t: "Suggest", d: "Shadow mode: it proposes a team", a: -90 },
  { t: "Review", d: "People label blind", a: 0 },
  { t: "Measure", d: "Tested on reviewed tickets", a: 90 },
  { t: "Certify", d: "Routes alone only after passing", a: 180 },
];

export function ReviewLoop() {
  return (
    <div className="grid items-center gap-10 lg:grid-cols-2">
      <div className="relative mx-auto aspect-square w-full max-w-[420px] sm:px-0">
        <svg viewBox="0 0 300 300" className="absolute inset-0 size-full" aria-hidden="true">
          <circle cx="150" cy="150" r="110" fill="none" stroke="var(--border)" strokeWidth="10" />
          <circle cx="150" cy="150" r="110" fill="none" stroke="var(--signal)" strokeWidth="2" strokeDasharray="2 9" strokeLinecap="round" opacity=".7" />
          <g className="orbit">
            <circle cx="150" cy="40" r="6" fill="var(--signal)" style={{ filter: "drop-shadow(0 0 6px var(--signal))" }} />
          </g>
        </svg>
        <div className="absolute left-1/2 top-1/2 grid size-24 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border bg-card shadow-[var(--shadow-panel)]">
          <MonolithMark size={48} className="text-foreground" />
        </div>
        <ol>
          {LOOP.map((n, i) => {
            const rad = (n.a * Math.PI) / 180;
            const x = 50 + Math.cos(rad) * 36.7;
            const y = 50 + Math.sin(rad) * 36.7;
            return (
              <li
                key={n.t}
                className="absolute w-[7.25rem] -translate-x-1/2 sm:w-[9.5rem] -translate-y-1/2 rounded-xl border bg-card px-3 py-2 text-center shadow-[var(--shadow-panel)]"
                style={{ left: `${x}%`, top: `${y}%` }}
              >
                <span className="block text-sm font-semibold">
                  <span className="sr-only">Step {i + 1}: </span>
                  {n.t}
                </span>
                <span className="block text-[13px] leading-snug text-muted-foreground">{n.d}</span>
              </li>
            );
          })}
        </ol>
      </div>
      <div className="rounded-3xl border bg-card p-6 sm:p-8">
        <p className="mono-label">A new workspace, on day one</p>
        <ul className="mt-5 divide-y">
          {[
            { on: true, t: "Suggests a team for every ticket", d: "Shown to the person triaging, with its evidence." },
            { on: true, t: "A person makes the call", d: "Every decision they make is a reviewed ticket." },
            { on: true, t: "Security always goes to a person", d: "In every mode, with no questions." },
            { on: false, t: "Routes on its own", d: "Locked until it passes a frozen test on your reviewed tickets." },
          ].map((r) => (
            <li key={r.t} className="flex gap-3 py-4 first:pt-0 last:pb-0">
              {r.on ? <CheckCircle2 aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ok" /> : <Lock aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-muted-foreground" />}
              <span>
                <span className="block font-semibold">
                  {r.t}
                  <span className="sr-only">{r.on ? " (on)" : " (locked)"}</span>
                </span>
                <span className="block text-sm text-muted-foreground">{r.d}</span>
              </span>
            </li>
          ))}
        </ul>
        <Link href="/evaluation" className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-signal underline underline-offset-4">
          See the evaluation lab <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Channels */

const MODES = {
  person: {
    label: "A person",
    Icon: UserRound,
    src: ["A person", "browser, any device"],
    entry: ["ResolveIT web app", "adds the key on the server"],
    out: ["Queue, question or person", "shown back with evidence"],
    note: "The browser never holds an API key. The web app signs each call on the server.",
  },
  agent: {
    label: "An AI agent",
    Icon: Bot,
    src: ["An AI agent", "any MCP client"],
    entry: ["MCP endpoint", "/mcp · agents propose only"],
    out: ["The same three outcomes", "with a receipt for the agent"],
    note: "Agents can file tickets and read the outcome. They never make the routing decision.",
  },
  api: {
    label: "Your systems",
    Icon: FileCode2,
    src: ["Your systems", "portal, chat or mail bridge"],
    entry: ["REST API", "POST /v1/incidents"],
    out: ["Decision and evidence", "in the JSON response"],
    note: "One tenant key per system. Same engine, same decision, same audit trail.",
  },
} as const;

function Node({ title, sub, hot, children }: { title: string; sub: string; hot?: boolean; children?: ReactNode }) {
  return (
    <div className={cn("relative rounded-xl border bg-card px-4 py-3", hot && "border-signal/70 shadow-[0_0_0_1px_var(--signal),0_16px_44px_-18px_var(--glow)]")}>
      {children}
      <p className="text-sm font-semibold">{title}</p>
      <p className="text-[13px] text-muted-foreground">{sub}</p>
    </div>
  );
}

function Arrow() {
  return (
    <div aria-hidden="true" className="relative mx-auto h-6 w-px overflow-hidden bg-border md:mx-0 md:h-px md:w-full">
      <span className="flow-dash absolute inset-0 bg-[repeating-linear-gradient(90deg,var(--signal)_0_6px,transparent_6px_12px)] opacity-80 max-md:bg-[repeating-linear-gradient(180deg,var(--signal)_0_6px,transparent_6px_12px)]" />
    </div>
  );
}

export function Channels() {
  const [mode, setMode] = useState<keyof typeof MODES>("person");
  const m = MODES[mode];
  return (
    <div>
      <div className="inline-flex flex-wrap gap-1 rounded-full border bg-card p-1" role="group" aria-label="How the ticket arrives">
        {(Object.keys(MODES) as (keyof typeof MODES)[]).map((k) => {
          const { label, Icon } = MODES[k];
          return (
            <button
              key={k}
              type="button"
              aria-pressed={k === mode}
              onClick={() => setMode(k)}
              className="inline-flex min-h-10 items-center gap-2 rounded-full px-4 text-sm text-muted-foreground transition-colors aria-pressed:bg-foreground aria-pressed:text-background"
            >
              <Icon aria-hidden="true" className="size-4" /> {label}
            </button>
          );
        })}
      </div>
      <div className="mt-6 space-y-5">
        <div className="rounded-2xl border border-dashed p-4 sm:p-5">
          <p className="mb-3 font-mono text-xs text-signal">ResolveIT boundary</p>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={mode}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="grid items-center gap-2 md:grid-cols-[1fr_2.5rem_1.2fr_2.5rem_1.3fr_2.5rem_1fr]"
            >
              <Node title={m.src[0]} sub={m.src[1]} />
              <Arrow />
              <Node title={m.entry[0]} sub={m.entry[1]} hot />
              <Arrow />
              <Node title="Decision engine" sub="rules · INT8 model · risk gate" />
              <Arrow />
              <Node title={m.out[0]} sub={m.out[1]} />
            </motion.div>
          </AnimatePresence>
          <p className="mt-4 text-[13px] text-muted-foreground">Every ticket is encrypted and saved before any model reads it.</p>
        </div>
        <p className="flex max-w-2xl items-start gap-2 text-sm leading-relaxed text-muted-foreground">
          <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-signal" /> {m.note}
        </p>
      </div>
    </div>
  );
}
