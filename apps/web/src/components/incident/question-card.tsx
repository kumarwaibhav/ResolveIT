"use client";

import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import type { QuestionView } from "@/lib/types";

interface Props {
  question: QuestionView;
  busy: boolean;
  onAnswer: (answer: string | null) => void;
}

/** One optional question. Skip is always available and is never the smaller button. */
export function QuestionCard({ question, busy, onAnswer }: Props) {
  const [choice, setChoice] = useState<string | null>(null);
  const group = useId();
  return (
    <form
      className="space-y-4 rounded-2xl border border-signal/30 bg-accent/50 p-4 sm:p-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (choice) onAnswer(choice);
      }}
    >
      <fieldset disabled={busy}>
        <legend className="text-lg font-bold tracking-[-0.02em]">{question.text}</legend>
        <p className="mt-1 text-sm text-muted-foreground">Optional. Your ticket is already saved.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {question.options.map((option) => (
            <label
              key={option.value}
              className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-full border bg-card px-4 text-sm font-medium transition-colors hover:border-foreground/30 has-checked:border-signal has-checked:bg-card has-checked:text-foreground has-checked:shadow-[0_0_0_3px_var(--glow)] has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring"
            >
              <input
                type="radio"
                name={group}
                value={option.value}
                checked={choice === option.value}
                onChange={() => setChoice(option.value)}
                className="accent-(--signal)"
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy || !choice} className="min-h-11 rounded-xl px-5">Send answer</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => onAnswer(null)} className="min-h-11 rounded-xl px-5">
          Skip
        </Button>
      </div>
    </form>
  );
}
