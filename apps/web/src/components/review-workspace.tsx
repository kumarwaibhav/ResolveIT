"use client";

import { useMemo, useState } from "react";
import { LocalDraftNotice, WorkspaceHeading } from "@/components/workspace-heading";
import { agreement, downloadJson, draftSplit, TEAMS } from "@/lib/workspaces";
import { LiveReviewWorkspace } from "@/components/live-review-workspace";

const RECORDS = [
  { id: "SYN-001", locale: "English", text: "VPN disconnects every few minutes since this morning. Everyone on the third floor is affected.", suggestion: "Network" },
  { id: "SYN-002", locale: "हिन्दी", text: "आज सुबह से पासवर्ड बदलने के बाद लॉगिन नहीं हो रहा है। बाकी टीम लॉगिन कर पा रही है।", suggestion: "Identity_Access" },
  { id: "SYN-003", locale: "Hinglish", text: "Laptop ka screen flicker ho raha hai, kal update ke baad se. External monitor pe sab theek hai.", suggestion: "Hardware_Endpoint" },
  { id: "SYN-004", locale: "English", text: "The finance dashboard is timing out. Other applications work. It started after the overnight database maintenance.", suggestion: "Database" },
];
type Rating = { a: string; b: string; adjudicated: string };
const empty = (): Rating => ({ a: "", b: "", adjudicated: "" });
const fmt = (value: number | null) => value === null ? "Undefined" : value.toFixed(3);

function PracticeReviewWorkspace() {
  const [index, setIndex] = useState(0), [blind, setBlind] = useState(true), [active, setActive] = useState<"a" | "b">("a");
  const [ratings, setRatings] = useState<Record<string, Rating>>({});
  const [identities, setIdentities] = useState({ a: "", b: "" });
  const [message, setMessage] = useState("");
  const record = RECORDS[index]!, rating = ratings[record.id] ?? empty();
  const independent = identities.a.trim() !== "" && identities.b.trim() !== "" && identities.a.trim() !== identities.b.trim();
  const pairs = useMemo(() => Object.values(ratings).filter((r) => r.a && r.b).map((r) => [r.a, r.b] as const), [ratings]);
  const metrics = agreement(pairs);
  const update = (field: keyof Rating, value: string) => setRatings((all) => ({ ...all, [record.id]: { ...rating, [field]: value } }));
  const completed = Object.values(ratings).filter((r) => r.a && r.b && (r.a === r.b || r.adjudicated)).length;
  return <>
    <WorkspaceHeading eyebrow="02 / REVIEW CONSOLE" title="Make judgment visible." description="Two independent labels. One traceable decision. Practice the gold-labeling workflow on clearly marked synthetic reports." ><span className="pill-status">Blind audit mode</span></WorkspaceHeading>
    <LocalDraftNotice />
    <div className="metric-grid"><div className="metric-card"><span>Overlapping label pairs</span><strong>{metrics.n}</strong><small>From your current session</small></div><div className="metric-card"><span>Cohen’s κ</span><strong>{fmt(metrics.kappa)}</strong><small>Undefined for empty or degenerate marginals</small></div><div className="metric-card"><span>Krippendorff’s α · nominal</span><strong>{fmt(metrics.alpha)}</strong><small>Two complete ratings per incident</small></div></div>
    <div className="workspace-grid">
      <section className="surface-panel"><div className="flex items-center justify-between gap-3"><span className="synthetic-tag">synthetic_seed</span><span className="panel-copy">{index + 1} / {RECORDS.length} · {record.locale}</span></div><p className="record-text" lang={record.locale === "हिन्दी" ? "hi" : "en"}>{record.text}</p><p className="panel-copy">{record.id} · Candidate split: <strong>{draftSplit(record.id)}</strong></p><label className="check-label"><input type="checkbox" checked={blind} onChange={(e) => setBlind(e.target.checked)} />Hide model suggestion until labels are recorded</label>{!blind && <p className="local-notice">Rule demonstration suggestion: {record.suggestion}. Revealing this invalidates a blind audit for this record.</p>}<div className="action-row"><button className="workspace-button" disabled={index === 0} onClick={() => setIndex(index - 1)}>← Previous</button><button className="workspace-button" disabled={index === RECORDS.length - 1} onClick={() => setIndex(index + 1)}>Next report →</button></div></section>
      <section className="surface-panel"><h2 className="panel-title">Independent annotation</h2><p className="panel-copy">Use distinct annotator identifiers. This local exercise cannot verify identities or enforce blinding across separate sessions.</p><div className="workspace-tabs" role="group" aria-label="Active annotator"><button aria-pressed={active === "a"} onClick={() => setActive("a")}>Annotator A</button><button aria-pressed={active === "b"} onClick={() => setActive("b")}>Annotator B</button></div><label className="field-label" htmlFor="annotator-id">Annotator {active.toUpperCase()} identifier</label><input id="annotator-id" className="field-input" value={identities[active]} onChange={(e) => setIdentities({ ...identities, [active]: e.target.value })} placeholder="Your staff identifier" maxLength={80} /><label className="field-label" htmlFor="review-team">Responsible team</label><select id="review-team" className="field-input" value={rating[active]} onChange={(e) => update(active, e.target.value)}><option value="">Choose a team…</option>{TEAMS.map((team) => <option key={team}>{team}</option>)}</select><p className="panel-copy mt-4">{rating.a && rating.b ? rating.a === rating.b ? "Both labels agree. Ready for reviewed draft export." : "Labels disagree. Adjudication required." : "Waiting for two labels. The other label stays hidden here."}</p>{rating.a && rating.b && rating.a !== rating.b && <><label className="field-label" htmlFor="adjudicate">Adjudicated team</label><select id="adjudicate" className="field-input" value={rating.adjudicated} onChange={(e) => update("adjudicated", e.target.value)}><option value="">Choose after independent review…</option>{TEAMS.map((team) => <option key={team}>{team}</option>)}</select></>}<div className="action-row"><button className="workspace-button primary" disabled={!independent || completed === 0} onClick={() => { downloadJson("resolveit-annotation-drafts.json", { schema_version: 1, provenance: "synthetic_seed", human_gold: false, persistence: "browser_draft", annotators: identities, blinding_enforced: false, agreement: metrics, records: RECORDS.filter((r) => { const label = ratings[r.id]; return label?.a && label?.b && (label.a === label.b || label.adjudicated); }).map((r) => ({ ...r, labels: ratings[r.id], candidate_split: draftSplit(r.id) })) }); setMessage(`Exported ${completed} synthetic annotation drafts. No human-gold promotion performed.`); }}>Export reviewed drafts</button></div>{!independent && <p className="panel-copy mt-3">Two distinct annotator identifiers required for export.</p>}<p role="status" className="success-message">{message}</p></section>
    </div>
    <section className="surface-panel mt-6"><h2 className="panel-title">From drafts to trustworthy gold</h2><div className="workflow-steps"><span>Independent identities</span><b aria-hidden="true">→</b><span>Blind labels</span><b aria-hidden="true">→</b><span>Adjudication</span><b aria-hidden="true">→</b><span>Locked incident groups</span><b aria-hidden="true">→</b><span>Frozen split registry</span></div><p className="panel-copy">Production gold collection requires authenticated reviewers, server-enforced blinding and immutable split storage. This synthetic practice workspace preserves provenance and does not certify real routing.</p></section>
  </>;
}

export function ReviewWorkspace() {
  const [practice, setPractice] = useState(false);
  return <><div className="workspace-tabs" role="group" aria-label="Review data source"><button aria-pressed={!practice} onClick={() => setPractice(false)}>Connected tenant</button><button aria-pressed={practice} onClick={() => setPractice(true)}>Synthetic practice</button></div>{practice ? <PracticeReviewWorkspace /> : <LiveReviewWorkspace />}</>;
}
