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
};

function headline(view: IncidentView, d: Decision): { title: string; detail: string } {
  if (view.state === "ERASED") return { title: "Erased", detail: "This incident's content was erased on request." };
  if (view.state === "ROUTED") {
    return { title: `Sent to ${team(view.routed_team)}`, detail: "The team has it now." };
  }
  if (view.state === "PENDING_CLARIFICATION") {
    return { title: "Ticket received", detail: "One optional question would help route it. You can skip it." };
  }
  const why = d.defer_reason ? DEFER_REASON[d.defer_reason] ?? "" : "";
  const hint = d.recommended_team ? ` Suggested team: ${team(d.recommended_team)}.` : "";
  return { title: "Sent to a person to triage", detail: `${why}${hint}` };
}

export function DecisionSummary({ view }: { view: IncidentView }) {
  const d = view.decision;
  if (!d) {
    return <p className="text-sm text-muted-foreground">{view.state === "ERASED" ? "This incident was erased." : "No decision recorded yet."}</p>;
  }
  const { title, detail } = headline(view, d);
  const top = Math.max(...d.probs);
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold tracking-tight" tabIndex={-1} data-result-heading>{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-muted-foreground">Top team probability</dt>
          <dd className="font-mono tabular-nums">{(top * 100).toFixed(0)}%</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Plausible teams</dt>
          <dd>
            {d.conformal.teams.length === 0
              ? "None"
              : d.conformal.teams.length > 4
                ? `${d.conformal.teams.length} of ${d.probs.length}, not narrowed yet`
                : d.conformal.teams.map(team).join(", ")}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Expected delay if routed</dt>
          <dd className="font-mono tabular-nums">{minutes(d.r_route)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Delay if a person triages</dt>
          <dd className="font-mono tabular-nums">{minutes(d.c_def)}</dd>
        </div>
      </dl>
      {d.no_ask_holdout ? (
        <p className="text-xs text-muted-foreground">This ticket is in the no-question comparison group.</p>
      ) : null}
    </div>
  );
}
