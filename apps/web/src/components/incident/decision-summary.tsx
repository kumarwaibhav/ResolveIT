"use client";

import { CircleHelp, Route, ShieldAlert, Trash2, UserRound } from "lucide-react";

import { GrowBar, RingGauge } from "@/components/motion";
import { cn } from "@/lib/utils";
import { TEAMS } from "@/lib/workspaces";
import type { Decision, IncidentView } from "@/lib/types";

const team = (name: string | null | undefined): string => (name ?? "").replaceAll("_", " ");
const minutes = (value: number | null | undefined): string =>
  value === null || value === undefined ? "not allowed" : `${Math.round(value)} min`;

const DEFER_REASON: Record<string, string> = {
  shadow_mode: "This workspace is in shadow mode. Routing is not yet certified on its own tickets, so a person decides.",
  no_conforming_team: "The message does not fit any team well enough.",
  risk_above_defer_cost: "Routing now carries more expected delay than asking a person.",
  set_too_large: "Too many teams remain plausible.",
  critical_contradiction: "Key details in the message conflict.",
  unmapped_queue: "The likely team has no mapped queue.",
  security_escalation: "Possible security incident. No questions were asked; a person reviews it now, flagged for the security team.",
  bundle_changed: "The model was updated while this question was open, so a person decides.",
};

type Tone = "route" | "ask" | "defer" | "security" | "erased";

function headline(view: IncidentView, d: Decision): { title: string; detail: string; tone: Tone } {
  if (view.state === "ERASED") return { title: "Erased", detail: "This incident's content was erased on request.", tone: "erased" };
  if (view.state === "ROUTED") return { title: `Sent to ${team(view.routed_team)}`, detail: "The team has it now, with the evidence below attached.", tone: "route" };
  if (view.state === "PENDING_CLARIFICATION") {
    return { title: "Ticket received", detail: "Saved. One optional question would help route it; you can skip it.", tone: "ask" };
  }
  const why = d.defer_reason ? DEFER_REASON[d.defer_reason] ?? "" : "";
  const hint = d.recommended_team ? ` Suggested team: ${team(d.recommended_team)}.` : "";
  return { title: "Sent to a person to triage", detail: `${why}${hint}`, tone: d.defer_reason === "security_escalation" ? "security" : "defer" };
}

const TONE: Record<Tone, { Icon: typeof Route; chip: string; label: string; box: string }> = {
  route: { Icon: Route, chip: "Routed", label: "ROUTE", box: "bg-primary text-primary-foreground" },
  ask: { Icon: CircleHelp, chip: "One question", label: "ASK", box: "bg-info-surface text-info" },
  defer: { Icon: UserRound, chip: "To a person", label: "DEFER", box: "bg-warn-surface text-warn" },
  security: { Icon: ShieldAlert, chip: "Security", label: "DEFER", box: "bg-risk-surface text-risk" },
  erased: { Icon: Trash2, chip: "Erased", label: "ERASED", box: "bg-muted text-muted-foreground" },
};

export function DecisionSummary({ view }: { view: IncidentView }) {
  const d = view.decision;
  if (!d) {
    return <p className="text-sm text-muted-foreground">{view.state === "ERASED" ? "This incident was erased." : "No decision recorded yet."}</p>;
  }
  const { title, detail, tone } = headline(view, d);
  const style = TONE[tone];
  const top = Math.max(...d.probs);
  const conformal = new Set(d.conformal.teams as string[]);
  const ranked = d.probs
    .map((p, i) => ({ name: TEAMS[i] ?? `team ${i}`, p }))
    .sort((a, b) => b.p - a.p)
    .slice(0, 5);
  const costMax = Math.max(d.r_route ?? 0, d.c_def ?? 0, 1);

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-4">
        <span className={cn("grid size-12 shrink-0 place-items-center rounded-2xl", style.box)} aria-hidden="true">
          <style.Icon className="size-6" />
        </span>
        <div className="min-w-0">
          <p className="mono-label">
            Decision · {style.label}
          </p>
          <h2 className="mt-1 text-2xl font-bold tracking-[-0.03em] outline-none" tabIndex={-1} data-result-heading>
            {title}
          </h2>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{detail}</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-[auto_1fr]">
        <div className="flex items-center gap-4 rounded-2xl border bg-card/70 p-4">
          <RingGauge value={top} size={88} stroke={8}>
            <span className="text-lg font-bold tabular">{(top * 100).toFixed(0)}%</span>
          </RingGauge>
          <div>
            <p className="mono-label">Top team probability</p>
            <div className="mt-1 text-sm font-semibold">{team(ranked[0]?.name)}</div>
            <div className="mt-0.5 max-w-[14rem] text-xs leading-relaxed text-muted-foreground">Calibrated, not a guarantee.</div>
          </div>
        </div>
        <div className="rounded-2xl border bg-card/70 p-4">
          <p className="mono-label">Plausible teams</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {d.conformal.teams.length === 0 ? (
              <span className="text-sm">None</span>
            ) : d.conformal.teams.length > 4 ? (
              <span className="text-sm">{`${d.conformal.teams.length} of ${d.probs.length}, not narrowed yet`}</span>
            ) : (
              d.conformal.teams.map((t) => (
                <span key={t} className="rounded-full border border-signal/40 bg-accent px-2.5 py-1 text-xs font-semibold text-accent-foreground">
                  {team(t)}
                </span>
              ))
            )}
          </div>
          <div className="mt-2 text-xs text-muted-foreground">The set that contains the right team about 90% of the time.</div>
        </div>
        <div className="rounded-2xl border bg-card/70 p-4 sm:col-span-2">
          <p className="mono-label mb-3">Expected delay · the trade-off behind the decision</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <p>Expected delay if routed</p>
                <div className="font-mono font-semibold tabular">{minutes(d.r_route)}</div>
              </div>
              <GrowBar value={(d.r_route ?? 0) / costMax} className="mt-2" barClassName={d.r_route === null ? "bg-muted" : "bg-primary"} />
            </div>
            <div>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <p>Delay if a person triages</p>
                <div className="font-mono font-semibold tabular">{minutes(d.c_def)}</div>
              </div>
              <GrowBar value={(d.c_def ?? 0) / costMax} className="mt-2" barClassName="bg-foreground/70" delay={0.1} />
            </div>
          </div>
        </div>
      </div>

      <div>
        <p className="mono-label mb-3">How likely each team is · top 5 of 12</p>
        <ul className="space-y-2.5">
          {ranked.map(({ name, p }, i) => (
            <li key={name} className="grid grid-cols-[minmax(0,9rem)_1fr_3rem] items-center gap-3 text-sm">
              <span className="truncate">
                {team(name)}
                {conformal.has(name) ? <span className="sr-only"> (in the plausible set)</span> : null}
              </span>
              <GrowBar value={p} delay={i * 0.05} barClassName={conformal.has(name) ? "bg-primary" : "bg-foreground/35"} />
              <span className="text-right font-mono text-xs tabular">{(p * 100).toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      </div>

      {d.no_ask_holdout ? <p className="text-xs text-muted-foreground">This ticket is in the no-question comparison group (about 1 in 10 tickets).</p> : null}
    </div>
  );
}
