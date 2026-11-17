"use client";
import { PageGuide } from "@/components/page-guide";
import { useEffect, useState } from "react";
import { CheckCircle2, CircleDashed } from "lucide-react";
import { NumberTicker, Reveal, RingGauge } from "@/components/motion";
import { LocalDraftNotice, WorkspaceHeading } from "@/components/workspace-heading";

const LADDER = [
  { name: "Training", done: true, note: "LoRA on mDeBERTa-v3" },
  { name: "Scaling", done: true, note: "Temperature on INT8 outputs" },
  { name: "Conformal fit", done: true, note: "Plausible-team sets" },
  { name: "Risk certification", done: true, note: "Per-queue, synthetic" },
  { name: "Frozen human test", done: false, note: "Needs reviewed tickets" },
];
import { workspaceApi, type EvaluationStatus } from "@/lib/workspace-api";
import { downloadJson, evaluatePredictions, type EvalRow, TEAMS } from "@/lib/workspaces";

type Report = ReturnType<typeof evaluatePredictions> & { provenance: string; baseline: string };
const BASELINES = [
  { name: "Majority class", detail: "Training-only class prior", status: "No frozen report" },
  { name: "Raw rules", detail: "Deterministic lexicon baseline", status: "No frozen report" },
  { name: "TF-IDF + linear", detail: "Classical text baseline", status: "No frozen report" },
  { name: "Three-head INT8 student", detail: "Shipped bundle inference", status: "No frozen report" },
];
export function EvaluationWorkspace() {
  const [live, setLive] = useState<EvaluationStatus | null>(null), [serviceError, setServiceError] = useState("");
  useEffect(() => { workspaceApi<EvaluationStatus>("evaluation").then(setLive).catch((err: unknown) => setServiceError(err instanceof Error ? err.message : "Evaluation service unavailable.")); }, []);
  const [report, setReport] = useState<Report | null>(null), [error, setError] = useState("");
  const load = async (file?: File) => {
    if (!file) return;
    try {
      if (file.size > 2_000_000) throw new Error("Prediction file exceeds 2 MB.");
      const data: unknown = JSON.parse(await file.text());
      if (!data || typeof data !== "object" || !("rows" in data) || !Array.isArray(data.rows) || !("provenance" in data) || typeof data.provenance !== "string") throw new Error("Expected {provenance, baseline, rows:[{label, probs}]}.");
      const rows = data.rows as EvalRow[];
      if (rows.some((row) => !row || typeof row !== "object" || typeof row.label !== "string" || !row.probs || typeof row.probs !== "object")) throw new Error("Every row requires label and probs.");
      const metrics = evaluatePredictions(rows);
      setReport({ ...metrics, provenance: data.provenance, baseline: "baseline" in data && typeof data.baseline === "string" ? data.baseline : "Uploaded predictions" }); setError("");
    } catch (err) { setReport(null); setError(err instanceof Error ? err.message : "Invalid prediction data."); }
  };
  return <><WorkspaceHeading eyebrow="04 · Evaluation lab" title="Confidence needs evidence." description="What the model has proved, on which data, and what it still has to prove before it may route a real customer's tickets on its own." /><PageGuide page="evaluation" /><LocalDraftNotice />{serviceError && <p role="alert" className="error-message mb-5">{serviceError}</p>}{live && <section className="surface-panel mb-6"><p className="eyebrow">CONNECTED BUNDLE</p><h2 className="panel-title break-all">{live.bundle_id}</h2><p className="panel-copy">{live.explanation}</p><div className="metric-grid"><div className="metric-card"><span>Bundle provenance</span><strong className="!text-base !tracking-normal">{live.provenance}</strong><small>{live.auto_route_enabled ? "Synthetic demo routing enabled" : "Human gate enabled"}</small></div><div className="metric-card"><span>Human gold incidents</span><strong><NumberTicker value={live.human_gold_count} /></strong><small>From persisted review outcomes</small></div><div className="metric-card"><span>Frozen human test support</span><strong><NumberTicker value={live.frozen_test_count} /></strong><small>{live.human_test_accuracy === null || live.human_test_accuracy === undefined ? "Metrics require a separate executed evaluation" : `Human test accuracy ${(live.human_test_accuracy * 100).toFixed(1)}%`}</small></div></div></section>}<section className="surface-panel"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="eyebrow">PRODUCTION CERTIFICATION</p><h2 className="panel-title">Human test report unavailable</h2><p className="panel-copy">No verified frozen human-gold report is connected to this workspace. Accuracy, routing lift and queue graduation remain unclaimed.</p></div><span className="pill-status">Shadow mode</span></div><ol className="my-6 grid gap-2 sm:grid-cols-5">{LADDER.map((step, i) => <li key={step.name} className={`relative rounded-2xl border p-4 ${step.done ? "bg-card" : "border-dashed"}`}><span className="flex items-center gap-2 text-sm font-semibold">{step.done ? <CheckCircle2 aria-hidden="true" className="size-4 text-ok" /> : <CircleDashed aria-hidden="true" className="size-4 text-muted-foreground" />}{step.name}<span className="sr-only">{step.done ? ": done" : ": not yet"}</span></span><span className="mt-1 block text-xs text-muted-foreground">{step.note}</span><span aria-hidden="true" className="absolute right-3 top-3 font-mono text-[10px] text-muted-foreground">{String(i + 1).padStart(2, "0")}</span></li>)}</ol><p className="panel-copy">Every threshold is fitted on the exact INT8 model that ships. The first four steps are complete on generated tickets; only a frozen test on a customer&apos;s own reviewed tickets can unlock automatic routing for them.</p></section><div className="workspace-grid mt-6"><section className="surface-panel"><h2 className="panel-title">Four explicit comparisons</h2><div tabIndex={0} className="data-table-wrap"><table className="data-table"><caption className="sr-only">Benchmark baseline availability</caption><thead><tr><th>Baseline</th><th>Evidence</th></tr></thead><tbody>{BASELINES.map((base) => <tr key={base.name}><td>{base.name}<small className="block text-muted-foreground mt-1">{base.detail}</small></td><td>{base.status}</td></tr>)}</tbody></table></div></section><section className="surface-panel"><h2 className="panel-title">Inspect prediction outputs</h2><p className="panel-copy">Compute accuracy, multiclass Brier and NLL from a supplied JSON file. Uploaded provenance is self-reported and is never treated as verified human gold.</p><label className="field-label" htmlFor="eval-file">Prediction JSON · maximum 2 MB</label><input id="eval-file" type="file" accept=".json,application/json" className="field-input" onChange={(e) => void load(e.target.files?.[0])} /><div className="action-row"><button className="workspace-button" onClick={() => downloadJson("resolveit-prediction-format.json", { provenance: "synthetic_seed", baseline: "format_example", rows: [{ label: "Network", probs: Object.fromEntries(TEAMS.map((team) => [team, team === "Network" ? 0.78 : 0.02])) }] })}>Download format example</button></div>{error && <p role="alert" className="error-message">{error}</p>}</section></div>{report && <Reveal as="section" className="mt-6"><div aria-live="polite"><p className="local-notice">Uploaded analysis · {report.baseline} · provenance: {report.provenance} (unverified). {report.n} rows. Does not certify deployment.</p><div className="metric-grid"><div className="metric-card flex items-center gap-4"><RingGauge value={report.accuracy} size={76} stroke={7}><span className="text-xs font-bold tabular">{(report.accuracy * 100).toFixed(0)}%</span></RingGauge><div><span>Uploaded accuracy</span><strong className="!mt-1">{(report.accuracy * 100).toFixed(2)}%</strong><small>Top-choice accuracy, not the routing policy</small></div></div><div className="metric-card"><span>Multiclass Brier</span><strong>{report.brier.toFixed(4)}</strong><small>Mean sum of squared class errors</small></div><div className="metric-card"><span>Negative log likelihood</span><strong>{report.nll.toFixed(4)}</strong><small>Natural log; probabilities clipped at 1e-15</small></div></div><button className="workspace-button" onClick={() => downloadJson("resolveit-uploaded-evaluation.json", { ...report, verified: false, certifies_routing: false })}>Export computed report</button></div></Reveal>}</>;
}
