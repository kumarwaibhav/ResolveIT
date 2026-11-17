"use client";

import { ShieldAlert } from "lucide-react";
import { useState } from "react";

import { DecisionSummary } from "@/components/incident/decision-summary";
import { EvidenceText } from "@/components/incident/evidence-text";
import { FrameTable, SlotGrid } from "@/components/incident/frame-table";
import { QuestionCard } from "@/components/incident/question-card";
import { GlassCard, Reveal } from "@/components/motion";
import type { IncidentView } from "@/lib/types";

interface Props {
  view: IncidentView;
  busy?: boolean;
  onAnswer?: (answer: string | null) => void;
}

export function IncidentPanel({ view, busy = false, onAnswer }: Props) {
  const [activeSlot, setActiveSlot] = useState<string | null>(null);
  const frame = view.frame ?? [];
  return (
    <div className="space-y-4">
      {view.security_trigger ? (
        <p role="status" className="flex items-center gap-2.5 rounded-2xl border border-risk/30 bg-risk-surface px-4 py-3 text-sm font-semibold text-risk">
          <ShieldAlert aria-hidden="true" className="size-4 shrink-0" />
          Possible security incident. Flagged for the Security team.
        </p>
      ) : null}
      <Reveal>
        <GlassCard className="space-y-6 p-5 sm:p-6">
          <DecisionSummary view={view} />
          {view.question && onAnswer ? <QuestionCard question={view.question} busy={busy} onAnswer={onAnswer} /> : null}
        </GlassCard>
      </Reveal>
      {view.text ? (
        <Reveal delay={0.05}>
          <section aria-labelledby="evidence-title" className="glass rounded-2xl p-5 sm:p-6">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 id="evidence-title" className="mono-label">What the message says</h3>
              <span className="text-xs text-muted-foreground">Underlined = evidence</span>
            </div>
            <EvidenceText text={view.text} frame={frame} activeSlot={activeSlot} onActivate={setActiveSlot} />
          </section>
        </Reveal>
      ) : null}
      {frame.length > 0 ? (
        <Reveal delay={0.1}>
          <section aria-labelledby="frame-title" className="glass space-y-5 rounded-2xl p-5 sm:p-6">
            <h3 id="frame-title" className="mono-label">Incident frame · 11 details</h3>
            <SlotGrid frame={frame} activeSlot={activeSlot} onActivate={setActiveSlot} />
            <FrameTable frame={frame} decision={view.decision ?? null} activeSlot={activeSlot} onActivate={setActiveSlot} />
          </section>
        </Reveal>
      ) : null}
      <p className="break-all font-mono text-[11px] text-muted-foreground">
        <span data-incident-id={view.id}>Incident {view.id}</span>
        {view.decision ? ` · bundle ${view.decision.bundle_id}` : ""}
      </p>
    </div>
  );
}
