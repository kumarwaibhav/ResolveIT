"use client";

import { CircleHelp, RotateCcw, Route, ShieldAlert, UserRound } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";

import { MonolithMark } from "@/components/brand/monolith";
import results from "@/generated/scenario-results.json";
import { evidenceSpans, SLOT_LABEL } from "@/lib/meter";
import { scenarioById } from "@/lib/scenarios";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { cn } from "@/lib/utils";
import { TEAM_LABEL } from "@/lib/workspaces";

type Outcome = "route" | "ask" | "person";

interface Pick {
  id: string;
  label: string;
}

/** Four real tickets. Every number below was recorded from the live engine, not written by hand. */
const PICKS: Pick[] = [
  { id: "mail-outlook", label: "A clear report" },
  { id: "vague-nothing", label: "A vague one, in Hinglish" },
  { id: "sec-phish", label: "A security incident" },
  { id: "erp-sap", label: "Too costly to guess" },
];

const LAYERS = ["Read", "Mask", "Model", "Decide", "Hand off"];
const STEP_MS = 420;
const DONE = LAYERS.length + 1;

interface Recorded {
  action: string;
  routed_team: string | null;
  recommended_team: string | null;
  defer_reason: string | null;
  question: string | null;
  top_p: number;
  plausible: string[];
  found: string[];
}

const RESULTS = (results as { verified_at: string; results: Record<string, Recorded> }).results;
const VERIFIED = new Date((results as { verified_at: string }).verified_at);

function outcomeOf(r: Recorded): Outcome {
  if (r.action === "ROUTE") return "route";
  if (r.action === "ASK") return "ask";
  return "person";
}

const BADGE: Record<Outcome, { text: (r: Recorded) => string; cls: string }> = {
  route: { text: (r) => `Routed · score ${r.top_p.toFixed(2)}`, cls: "border-ok/40 bg-ok-surface text-ok" },
  ask: { text: () => "One question asked", cls: "border-info/40 bg-info-surface text-info" },
  person: { text: (r) => (r.defer_reason === "security_escalation" ? "To a person · security" : "To a person · risk too high"), cls: "border-risk/40 bg-risk-surface text-risk" },
};

function summary(r: Recorded): [string, string] {
  const o = outcomeOf(r);
  if (o === "route") return ["Routed and explained.", `It lands in ${TEAM_LABEL[r.routed_team ?? ""] ?? r.routed_team}'s queue with the words that decided it.`];
  if (o === "ask") return ["Asked, not guessed.", `${r.plausible.length} teams were still plausible, so it asked the reporter one question in their own language.`];
  if (r.defer_reason === "security_escalation") return ["Escalated, no questions.", "A security signal skips every question and goes straight to a person."];
  return ["Handed to a person.", `A wrong route here would cost more than a person checking. Its suggestion, ${TEAM_LABEL[r.recommended_team ?? ""] ?? r.recommended_team}, goes with it.`];
}

/** The ticket text with the exact words the rules read marked in place. */
function Marked({ text }: { text: string }) {
  const spans = evidenceSpans(text);
  const parts: React.ReactNode[] = [];
  let at = 0;
  spans.forEach((s, i) => {
    if (s.start > at) parts.push(<Fragment key={`t${i}`}>{text.slice(at, s.start)}</Fragment>);
    parts.push(
      <mark key={`m${i}`} className="evidence-mark bg-transparent" title={SLOT_LABEL[s.slot] ?? s.slot}>
        {text.slice(s.start, s.end)}
        <span className="sr-only"> ({SLOT_LABEL[s.slot] ?? s.slot})</span>
      </mark>,
    );
    at = s.end;
  });
  if (at < text.length) parts.push(<Fragment key="end">{text.slice(at)}</Fragment>);
  return <>{parts}</>;
}

/** Five isometric layers, drawn in SVG so the geometry is exact at every size. */
function LayerStack({ phase }: { phase: number }) {
  const cx = 120;
  const w = 104;
  const h = 44;
  const t = 9;
  const gap = 42;
  const top = 50;
  const reduce = useReducedMotion();
  const active = Math.min(phase, LAYERS.length) - 1;
  return (
    <svg viewBox="0 0 330 290" className="h-auto w-full max-w-[380px]" aria-hidden="true">
      {[...LAYERS.keys()].reverse().map((i) => {
        const cy = top + i * gap;
        const on = i === active;
        const lit = i < phase;
        return (
          <g key={i} style={{ transition: "opacity .4s" }} opacity={lit || phase === 0 ? 1 : 0.55}>
            <polygon points={`${cx - w},${cy} ${cx},${cy + h} ${cx},${cy + h + t} ${cx - w},${cy + t}`} fill="var(--muted)" stroke="var(--border)" />
            <polygon points={`${cx},${cy + h} ${cx + w},${cy} ${cx + w},${cy + t} ${cx},${cy + h + t}`} fill="var(--secondary)" stroke="var(--border)" />
            <polygon
              points={`${cx},${cy - h} ${cx + w},${cy} ${cx},${cy + h} ${cx - w},${cy}`}
              fill={on ? "color-mix(in srgb, var(--card) 66%, var(--signal) 34%)" : lit ? "color-mix(in srgb, var(--card) 88%, var(--signal) 12%)" : "var(--card)"}
              stroke={on ? "var(--signal)" : lit ? "color-mix(in srgb, var(--signal) 55%, transparent)" : "var(--input)"}
              strokeWidth={on ? 1.8 : 1}
              style={{ transition: "fill .35s, stroke .35s", filter: on ? "drop-shadow(0 0 14px var(--glow))" : undefined }}
            />
            <line x1={cx + w + 6} y1={cy} x2={cx + w + 22} y2={cy} stroke={lit ? "var(--signal)" : "var(--border)"} />
            <text x={cx + w + 28} y={cy + 4} className="font-mono" fontSize="11" fill={lit ? "var(--foreground)" : "var(--muted-foreground)"} letterSpacing=".06em">
              {String(i + 1).padStart(2, "0")} {LAYERS[i]!.toUpperCase()}
            </text>
          </g>
        );
      })}
      {phase > 0 && phase <= LAYERS.length ? (
        <motion.circle
          r="5"
          cx={cx}
          fill="var(--signal)"
          initial={false}
          animate={{ cy: top + active * gap }}
          transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 220, damping: 24 }}
          style={{ filter: "drop-shadow(0 0 8px var(--signal))" }}
        />
      ) : null}
    </svg>
  );
}

function Panel({ Icon, title, idle, on, typing, children }: { Icon: typeof Route; title: string; idle: string; on: boolean; typing: boolean; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-2xl border bg-card/80 p-4 transition-[border-color,box-shadow] duration-500",
        on ? "border-signal/60 shadow-[0_0_0_1px_var(--signal),0_18px_50px_-20px_var(--glow)]" : "",
      )}
    >
      <p className="flex items-center gap-2 text-[13px] font-medium text-muted-foreground">
        <Icon aria-hidden="true" className={cn("size-3.5", on && "text-signal")} /> {title}
      </p>
      <div className="mt-2 min-h-11 text-sm">
        {on && typing ? (
          <span className="inline-flex gap-1 rounded-full bg-muted px-3 py-2" aria-hidden="true">
            {[0, 1, 2].map((d) => (
              <span key={d} className="size-1.5 animate-pulse rounded-full bg-muted-foreground" style={{ animationDelay: `${d * 150}ms` }} />
            ))}
          </span>
        ) : on ? (
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
            {children}
          </motion.div>
        ) : (
          <span className="text-muted-foreground">{idle}</span>
        )}
      </div>
    </div>
  );
}

export function TriageDemo() {
  const [pick, setPick] = useState(PICKS[0]!.id);
  const [phase, setPhase] = useState(0);
  const reduce = useReducedMotion();
  const timers = useRef<number[]>([]);
  const root = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  const run = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (reduce) {
      setPhase(DONE);
      return;
    }
    setPhase(0);
    for (let p = 1; p <= DONE; p++) timers.current.push(window.setTimeout(() => setPhase(p), p * STEP_MS + (p === DONE ? 380 : 0)));
  }, [reduce]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  // First run starts when the demo scrolls into view.
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e?.isIntersecting && !started.current) {
          started.current = true;
          run();
        }
      },
      { threshold: 0.35 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [run]);

  const choose = (id: string) => {
    started.current = true;
    setPick(id);
    run();
  };

  const scenario = scenarioById(pick)!;
  const r = RESULTS[pick]!;
  const outcome = outcomeOf(r);
  const done = phase >= DONE;
  const scoring = phase >= 3;
  const typing = phase === LAYERS.length;
  const [lead, rest] = summary(r);
  const badge = BADGE[outcome];

  return (
    <div ref={root}>
      <fieldset>
        <legend className="mono-label">Pick a ticket</legend>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {PICKS.map((p) => {
            const s = scenarioById(p.id)!;
            const on = p.id === pick;
            return (
              <button
                key={p.id}
                type="button"
                aria-pressed={on}
                onClick={() => choose(p.id)}
                className={cn(
                  "rounded-2xl border p-4 text-left transition-colors",
                  on ? "border-signal/70 bg-[color-mix(in_srgb,var(--card)_80%,var(--signal)_20%)]" : "bg-card/60 hover:bg-card",
                )}
              >
                <span className="block text-sm font-semibold">{p.label}</span>
                <span className="mt-1 line-clamp-2 block text-[13px] leading-relaxed text-muted-foreground">“{s.text}”</span>
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="mt-10 grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] lg:gap-6">
        <div className="flex justify-center lg:justify-start">
          <LayerStack phase={phase} />
        </div>

        <div className="flex items-center gap-4 lg:flex-col lg:gap-3">
          <div className="relative grid size-20 place-items-center rounded-full border bg-card">
            {phase > 0 && !done ? <span aria-hidden="true" className="pulse-ring absolute inset-0 rounded-full border border-signal" /> : null}
            <MonolithMark size={40} className="text-foreground" />
          </div>
          <div className="lg:text-center">
            <p className="mono-label">Top team score</p>
            <p className="text-3xl font-semibold tabular tracking-[-0.03em]">{scoring ? r.top_p.toFixed(2) : "—"}</p>
            <p className="text-[13px] text-muted-foreground">{scoring ? `${r.plausible.length} plausible ${r.plausible.length === 1 ? "team" : "teams"}` : "Reading…"}</p>
          </div>
        </div>

        <div className="space-y-2.5">
          <Panel Icon={Route} title="Team queue" idle="Standing by" on={phase >= LAYERS.length && outcome === "route"} typing={typing}>
            <span className="font-semibold">{TEAM_LABEL[r.routed_team ?? ""]}</span>
            <span className="block text-[13px] text-muted-foreground">Evidence attached: {r.found.map((f) => SLOT_LABEL[f] ?? f).join(", ")}</span>
          </Panel>
          <Panel Icon={CircleHelp} title="One question to the reporter" idle="Not needed yet" on={phase >= LAYERS.length && outcome === "ask"} typing={typing}>
            <span className="font-semibold" lang="hi-Latn">“{r.question}”</span>
            <span className="block text-[13px] text-muted-foreground">Which system or app is this about?</span>
          </Panel>
          <Panel
            Icon={r.defer_reason === "security_escalation" ? ShieldAlert : UserRound}
            title="A person on the service desk"
            idle="Standing by"
            on={phase >= LAYERS.length && outcome === "person"}
            typing={typing}
          >
            <span className="font-semibold">{r.defer_reason === "security_escalation" ? "Flagged for Security" : `Suggested: ${TEAM_LABEL[r.recommended_team ?? ""]}`}</span>
            <span className="block text-[13px] text-muted-foreground">
              {r.defer_reason === "security_escalation" ? "No questions asked of the reporter." : "The person decides. The suggestion saves them time."}
            </span>
          </Panel>
        </div>
      </div>

      <div className="mt-10 border-t pt-6">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-muted-foreground">
            The ticket · {scenario.who} · {scenario.channel}
          </p>
          <AnimatePresence>
            {done ? (
              <motion.span initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className={cn("rounded-full border px-2.5 py-0.5 text-xs font-semibold", badge.cls)}>
                {badge.text(r)}
              </motion.span>
            ) : null}
          </AnimatePresence>
          <button type="button" onClick={run} className="ml-auto inline-flex min-h-10 items-center gap-1.5 rounded-full border px-3 text-[13px] font-medium text-muted-foreground hover:text-foreground">
            <RotateCcw aria-hidden="true" className="size-3.5" /> Replay
          </button>
        </div>
        <p lang={scenario.locale === "en" ? "en" : scenario.locale === "hi" ? "hi" : "hi-Latn"} className="mt-3 max-w-3xl text-[clamp(1.15rem,2.2vw,1.5rem)] leading-relaxed text-muted-foreground">
          <Marked text={scenario.text} />
        </p>
        <p className="mt-4 text-sm text-muted-foreground" role="status">
          {done ? (
            <>
              <strong className="font-semibold text-foreground">{lead}</strong> {rest}
            </>
          ) : (
            <span className="sr-only">Working through the five layers.</span>
          )}
        </p>
        <p className="mt-2 text-[13px] text-muted-foreground">
          Recorded from the live engine on {VERIFIED.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })}. Underlined: the words the rules read.
        </p>
      </div>
    </div>
  );
}
