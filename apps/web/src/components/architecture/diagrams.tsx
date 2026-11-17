"use client";

import { AnimatePresence, motion, useInView } from "motion/react";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import { Pause, Play } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/* ─────────────────────────── System map ─────────────────────────── */

const NODES = [
  { id: "people", x: 70, y: 80, w: 150, t: "People", s: "Browser, any device", d: "Employees and service-desk staff use the web app. The browser never holds an API key." },
  { id: "agents", x: 70, y: 300, w: 150, t: "AI agents", s: "MCP clients", d: "Agents file tickets through the Model Context Protocol. Their answers count only when they quote the user." },
  { id: "web", x: 300, y: 80, w: 190, t: "Web app", s: "Next.js · Vercel Mumbai", d: "Serves the interface and acts as a backend-for-frontend: it checks origin and session, then adds the key on the server." },
  { id: "api", x: 560, y: 190, w: 190, t: "Decision API", s: "FastAPI · Modal", d: "Owns every decision: saves the ticket, reads it, scores teams, runs the risk gate, records the audit trail." },
  { id: "db", x: 830, y: 80, w: 160, t: "Postgres 16", s: "Neon · row-level security", d: "Every tenant table enforces row-level security. Reports are encrypted before they are stored." },
  { id: "model", x: 830, y: 300, w: 160, t: "Model bundle", s: "INT8 ONNX · 315 MB", d: "Model, thresholds and costs in one package, verified by SHA-256 before it serves a single ticket." },
] as const;
const EDGES = [
  { id: "e1", d: "M220 105 H300", hot: true },
  { id: "e2", d: "M490 105 C530 105 520 215 560 215", hot: true },
  { id: "e3", d: "M220 325 C400 325 480 230 560 230", hot: false },
  { id: "e4", d: "M750 205 C790 205 790 105 830 105", hot: false },
  { id: "e5", d: "M750 230 C790 230 790 325 830 325", hot: true },
];

export function SystemMap() {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [sel, setSel] = useState<string>("api");
  const [live, setLive] = useState(true);
  const reduce = useReducedMotion();
  const moving = live && !reduce;
  const node = NODES.find((n) => n.id === sel)!;
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
      <div className="min-w-0 space-y-3">
        <div className="overflow-x-auto rounded-2xl border bg-card/60 p-2" role="region" tabIndex={0} aria-label="System map, scrollable">
          <svg viewBox="0 0 1020 420" className="h-auto w-full min-w-[640px]" role="group" aria-label="System map. Select a component to read about it.">
            <defs>
              <pattern id={`${uid}dots`} width="20" height="20" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="1" fill="var(--grid-dot)" />
              </pattern>
              <marker id={`${uid}arrow`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M0 0L10 5L0 10z" fill="var(--signal)" />
              </marker>
            </defs>
            <rect width="1020" height="420" fill={`url(#${uid}dots)`} rx="16" />
            {EDGES.map((e, i) => (
              <g key={e.id}>
                {e.hot ? (
                  <path id={`${uid}${e.id}`} d={e.d} fill="none" stroke="var(--signal)" strokeWidth="3" markerEnd={`url(#${uid}arrow)`} />
                ) : (
                  <path id={`${uid}${e.id}`} d={e.d} fill="none" stroke="var(--muted-foreground)" strokeWidth="2" strokeDasharray="6 7" className={moving ? "flow-dash" : undefined} />
                )}
                {moving ? (
                  <circle r="5" fill={e.hot ? "var(--signal)" : "var(--foreground)"}>
                    <animateMotion dur={`${2.2 + i * 0.3}s`} repeatCount="indefinite" rotate="auto">
                      <mpath href={`#${uid}${e.id}`} />
                    </animateMotion>
                  </circle>
                ) : null}
              </g>
            ))}
            {NODES.map((n) => {
              const on = n.id === sel;
              return (
                <g
                  key={n.id}
                  role="button"
                  tabIndex={0}
                  aria-pressed={on}
                  aria-label={`${n.t}: ${n.s}`}
                  onClick={() => setSel(n.id)}
                  onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setSel(n.id))}
                  className="group cursor-pointer outline-none"
                >
                  <rect x={n.x - 5} y={n.y - 5} width={n.w + 10} height="80" rx="20" fill="none" stroke="var(--ring)" strokeWidth="3" strokeDasharray="7 5" className="opacity-0 group-focus-visible:opacity-100" />
                  <rect x={n.x} y={n.y} width={n.w} height="70" rx="16" fill="var(--card)" stroke={on ? "var(--signal)" : "var(--border)"} strokeWidth={on ? 2.5 : 1.2} style={{ filter: on ? "drop-shadow(0 10px 24px var(--glow))" : undefined }} />
                  <text x={n.x + 16} y={n.y + 31} fontSize="18" fontWeight="700" fill="var(--foreground)">{n.t}</text>
                  <text x={n.x + 16} y={n.y + 54} fontSize="14" fill="var(--muted-foreground)">{n.s.length > 22 ? `${n.s.slice(0, 21)}…` : n.s}</text>
                </g>
              );
            })}
            <text x="395" y="168" fontSize="14" fill="var(--muted-foreground)" textAnchor="middle">key added on the server</text>
          </svg>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <p className="flex flex-wrap items-center gap-x-5 gap-y-1">
            <span className="inline-flex items-center gap-2"><span aria-hidden="true" className="h-[3px] w-6 rounded-full bg-signal" /> Solid line with arrow: the path a ticket takes</span>
            <span className="inline-flex items-center gap-2"><span aria-hidden="true" className="w-6 border-t-2 border-dashed border-muted-foreground" /> Dashed: agent and data traffic</span>
          </p>
          {!reduce ? (
            <button type="button" onClick={() => setLive((v) => !v)} aria-pressed={!live} className="workspace-button !min-h-10">
              {live ? <Pause aria-hidden="true" className="size-4" /> : <Play aria-hidden="true" className="size-4" />}
              {live ? "Pause motion" : "Play motion"}
            </button>
          ) : null}
        </div>
      </div>
      <div className="self-start" aria-live="polite">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={node.id} initial={reduce ? false : { opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={reduce ? { opacity: 1 } : { opacity: 0, x: -8 }} transition={{ duration: 0.2 }} className="glass rounded-2xl p-5">
            <p className="mono-label">Component</p>
            <h3 className="mt-1 text-xl font-bold tracking-[-0.02em]">{node.t}</h3>
            <p className="text-sm font-medium text-signal">{node.s}</p>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{node.d}</p>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ─────────────────────────── Request lifecycle (sequence) ─────────────────────────── */

const LANES = ["Browser", "Web app", "Decision API", "Database", "Model"];
const STEPS = [
  { from: 0, to: 1, t: "Send ticket", d: "Same-origin POST. The browser sends text only, never a key." },
  { from: 1, to: 2, t: "Add credentials", d: "The web app opens the sealed session and adds the bearer key." },
  { from: 2, to: 3, t: "Save first", d: "The report is encrypted and stored before any analysis." },
  { from: 2, to: 2, t: "Read and mask", d: "Rules extract the 11 details; personal data is masked." },
  { from: 2, to: 4, t: "Score teams", d: "The INT8 encoder returns probabilities for all 12 teams." },
  { from: 2, to: 2, t: "Risk gate", d: "Calibration, plausible-team set and the risk certificate decide." },
  { from: 2, to: 3, t: "Record decision", d: "Decision, evidence and bundle ID are written to the audit trail." },
  { from: 2, to: 0, t: "Show the result", d: "Route, one question, or a person, with the evidence attached." },
];

export function RequestLifecycle() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { amount: 0.4 });
  const reduce = useReducedMotion();
  const [step, setStep] = useState(reduce ? STEPS.length - 1 : 0);
  const [playing, setPlaying] = useState(!reduce);
  useEffect(() => {
    if (!playing || !inView || reduce) return;
    const t = setInterval(() => setStep((s) => (s + 1) % STEPS.length), 1500);
    return () => clearInterval(t);
  }, [playing, inView, reduce]);
  const W = 860;
  const laneX = (i: number) => 70 + i * ((W - 140) / (LANES.length - 1));
  const rowY = (i: number) => 70 + i * 42;
  return (
    <div ref={ref} className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="min-w-0 overflow-x-auto rounded-2xl border bg-card/60 p-2" role="region" tabIndex={0} aria-label="Sequence diagram, scrollable">
        <svg viewBox={`0 0 ${W} ${rowY(STEPS.length) + 10}`} className="h-auto w-full min-w-[620px]" role="img" aria-label="Sequence of one ticket from the browser through the web app, API, database and model, and back.">
          {LANES.map((l, i) => (
            <g key={l}>
              <rect x={laneX(i) - 58} y="10" width="116" height="34" rx="10" fill="var(--card)" stroke="var(--border)" />
              <text x={laneX(i)} y="32" textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--foreground)">{l}</text>
              <line x1={laneX(i)} x2={laneX(i)} y1="44" y2={rowY(STEPS.length)} stroke="var(--border)" strokeDasharray="4 6" />
            </g>
          ))}
          {STEPS.map((s, i) => {
            const y = rowY(i) + 14;
            const on = i === step;
            const seen = i <= step;
            const self = s.from === s.to;
            const x1 = laneX(s.from);
            const x2 = laneX(s.to);
            const color = on ? "var(--signal)" : seen ? "var(--foreground)" : "var(--border)";
            return (
              <g key={s.t} opacity={seen ? 1 : 0.5}>
                {self ? (
                  <path d={`M${x1} ${y - 8} h40 v16 h-40`} fill="none" stroke={color} strokeWidth={on ? 2.5 : 1.5} markerEnd="" />
                ) : (
                  <line x1={x1} x2={x2 + (x2 > x1 ? -6 : 6)} y1={y} y2={y} stroke={color} strokeWidth={on ? 2.5 : 1.5} />
                )}
                {!self ? <path d={x2 > x1 ? `M${x2 - 8} ${y - 5} L${x2} ${y} L${x2 - 8} ${y + 5}` : `M${x2 + 8} ${y - 5} L${x2} ${y} L${x2 + 8} ${y + 5}`} fill="none" stroke={color} strokeWidth="2" /> : null}
                <text x={self ? x1 + 48 : (x1 + x2) / 2} y={y - 8} textAnchor={self ? "start" : "middle"} fontSize="12" fontWeight={on ? 700 : 500} fill={on ? "var(--signal)" : "var(--muted-foreground)"}>
                  {i + 1}. {s.t}
                </text>
                {on && !reduce ? (
                  <motion.circle key={`p${step}`} r="5" fill="var(--signal)" cy={y} initial={{ cx: x1 }} animate={{ cx: self ? x1 + 40 : x2 }} transition={{ duration: 0.9, ease: "easeInOut" }} />
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setPlaying((p) => !p)} className="workspace-button !min-h-10" aria-pressed={playing}>
            {playing ? <Pause aria-hidden="true" className="size-4" /> : <Play aria-hidden="true" className="size-4" />}
            {playing ? "Pause" : "Play"}
          </button>
          <span className="font-mono text-xs text-muted-foreground">Step {step + 1} of {STEPS.length}</span>
        </div>
        <ol className="space-y-1.5">
          {STEPS.map((s, i) => (
            <li key={s.t}>
              <button
                type="button"
                onClick={() => (setStep(i), setPlaying(false))}
                aria-current={i === step ? "step" : undefined}
                className={cn("w-full rounded-xl border px-3 py-2 text-left transition-colors", i === step ? "border-signal/50 bg-card" : "border-transparent hover:bg-card/60")}
              >
                <span className="text-sm font-semibold">{i + 1}. {s.t}</span>
                {i === step ? <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">{s.d}</span> : null}
              </button>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

/* ─────────────────────────── Decision engine ─────────────────────────── */

const ENGINE = [
  { t: "Rules", s: "11 details + evidence", tone: "" },
  { t: "Mask", s: "PII hidden", tone: "" },
  { t: "Encoder", s: "INT8 mDeBERTa", tone: "" },
  { t: "Calibrate", s: "Honest probabilities", tone: "" },
  { t: "Plausible set", s: "~90% coverage", tone: "" },
  { t: "Risk gate", s: "≤ 5% misroute", tone: "hot" },
];

export function DecisionEngine() {
  return (
    <div>
      <ol className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {ENGINE.map((e, i) => (
          <li
            key={e.t}
            className={cn("scroll-reveal relative rounded-2xl border p-4", e.tone ? "border-signal/50 bg-accent" : "bg-card/70")}
            data-i={i}
          >
            <span className="font-mono text-[10px] text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
            <p className="mt-2 font-bold">{e.t}</p>
            <p className="text-xs text-muted-foreground">{e.s}</p>
          </li>
        ))}
      </ol>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {[
          { t: "Route", s: "Certificate holds for one team", c: "bg-primary text-primary-foreground" },
          { t: "Ask", s: "One answer is worth the wait", c: "bg-info-surface text-info" },
          { t: "Hand off", s: "Unsure, conflicting, or security", c: "bg-risk-surface text-risk" },
        ].map((o, i) => (
          <div
            key={o.t}
            data-i={i}
            className={cn("scroll-reveal rounded-2xl p-4", o.c)}
          >
            <p className="text-lg font-bold">{o.t}</p>
            <p className="text-xs">{o.s}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─────────────────────────── Security layers ─────────────────────────── */

const LAYERS = [
  { t: "Browser", d: "Strict CSP, no framing, HSTS, no-store caching" },
  { t: "Web app", d: "Same-origin only; cross-site requests refused" },
  { t: "Session", d: "API key sealed with AES-GCM, 1-hour expiry" },
  { t: "API", d: "Per-person keys, role checks on every endpoint" },
  { t: "Database", d: "Row-level security, enforced even for the app" },
  { t: "Data", d: "Reports encrypted; identifiers masked for models" },
];

export function SecurityLayers() {
  const [sel, setSel] = useState(LAYERS.length - 1);
  return (
    <div className="grid items-center gap-8 lg:grid-cols-2">
      <div className="relative mx-auto aspect-square w-full max-w-[380px]" aria-hidden="true">
        {LAYERS.map((l, i) => {
          const inset = i * 8;
          const on = i === sel;
          return (
            <div
              key={l.t}
              className={cn("absolute rounded-full border transition-colors duration-300", on ? "border-signal bg-accent/60" : "bg-card/30")}
              style={{ inset: `${inset}%` }}
              />
          );
        })}
        <div className="absolute inset-[44%] grid place-items-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">DATA</div>
      </div>
      <ol className="space-y-2">
        {LAYERS.map((l, i) => (
          <li key={l.t}>
            <button
              type="button"
              aria-pressed={i === sel}
              onClick={() => setSel(i)}
              onMouseEnter={() => setSel(i)}
              className={cn("flex w-full items-start gap-3 rounded-2xl border px-4 py-3 text-left transition-colors", i === sel ? "border-signal/50 bg-card" : "border-transparent hover:bg-card/60")}
            >
              <span className="font-mono text-xs text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
              <span>
                <span className="block text-sm font-bold">{l.t}</span>
                <span className="block text-sm text-muted-foreground">{l.d}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
