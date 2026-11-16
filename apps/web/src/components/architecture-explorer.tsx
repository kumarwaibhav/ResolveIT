"use client";
import { useState } from "react";

const STAGES = [
  { name: "Raw evidence", title: "Keep the original meaning", detail: "Deterministic rules read the original report first. Protected error codes survive masking. Evidence spans refer to raw Unicode code points." },
  { name: "PII shield", title: "Minimize what the model sees", detail: "Normalize and mask detected identifiers before neural processing. Offset maps connect normalized and masked spans back to source evidence. Raw reports are encrypted separately." },
  { name: "Model bundle", title: "Version the whole decision", detail: "A deployable bundle binds model, tokenizer, class order, temperature, thresholds, costs and policy. Synthetic smoke outputs do not establish real-world accuracy." },
  { name: "Risk gate", title: "Know when to stop", detail: "Conformal support, certified queue risk, critical slots and expected cost control routing. Empty sets defer. Real tenants without sufficient human evidence stay in shadow mode." },
  { name: "Human / agent", title: "A considered handoff", detail: "Ask at most one question or defer to a person. Enterprise agent assertions need source citations and signed request state. Standard MCP clients use negotiated lifecycle and tools." },
];
export function ArchitectureExplorer() {
  const [selected, setSelected] = useState(0);
  const current = STAGES[selected]!;
  return <section className="surface-panel"><p className="eyebrow">SYSTEM EXPLORER</p><h2 className="panel-title">Trace the decision path</h2><div className="architecture-track" role="group" aria-label="Explore pipeline stage">{STAGES.map((stage, idx) => <button key={stage.name} onClick={() => setSelected(idx)} aria-pressed={selected === idx}><span>{String(idx + 1).padStart(2, "0")}</span><strong>{stage.name}</strong><svg viewBox="0 0 80 22" aria-hidden="true"><path d="M0 11h65m-8-6 8 6-8 6" /></svg></button>)}</div><div className="architecture-description" aria-live="polite"><h3>{current.title}</h3><p className="panel-copy">{current.detail}</p></div></section>;
}
