"use client";

import { useState } from "react";

import { DecisionSummary } from "@/components/incident/decision-summary";
import { EvidenceText } from "@/components/incident/evidence-text";
import { FrameTable } from "@/components/incident/frame-table";
import { QuestionCard } from "@/components/incident/question-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
        <p role="status" className="rounded-md bg-risk-surface px-3 py-2 text-sm font-medium text-risk">
          Possible security incident. Flagged for the Security team.
        </p>
      ) : null}
      <Card>
        <CardContent className="space-y-4">
          <DecisionSummary view={view} />
          {view.question && onAnswer ? <QuestionCard question={view.question} busy={busy} onAnswer={onAnswer} /> : null}
        </CardContent>
      </Card>
      {view.text ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">What the message says</CardTitle>
          </CardHeader>
          <CardContent>
            <EvidenceText text={view.text} frame={frame} activeSlot={activeSlot} onActivate={setActiveSlot} />
          </CardContent>
        </Card>
      ) : null}
      {frame.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">Details</CardTitle>
          </CardHeader>
          <CardContent>
            <FrameTable frame={frame} decision={view.decision ?? null} activeSlot={activeSlot} onActivate={setActiveSlot} />
          </CardContent>
        </Card>
      ) : null}
      <p className="font-mono text-xs text-muted-foreground">
        <span data-incident-id={view.id}>Incident {view.id}</span>
        {view.decision ? ` · bundle ${view.decision.bundle_id}` : ""}
      </p>
    </div>
  );
}
