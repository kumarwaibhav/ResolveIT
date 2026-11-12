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
      className="space-y-4 rounded-lg border border-signal/40 bg-accent/40 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (choice) onAnswer(choice);
      }}
    >
      <fieldset disabled={busy}>
        <legend className="text-base font-medium">{question.text}</legend>
        <p className="mt-1 text-sm text-muted-foreground">Optional. Your ticket is already saved.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {question.options.map((option) => (
            <label
              key={option.value}
              className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-md border bg-card px-3 text-sm has-checked:border-signal has-checked:bg-accent has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring sm:min-h-9"
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
        <Button type="submit" disabled={busy || !choice} className="min-h-11 sm:min-h-9">Send answer</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => onAnswer(null)} className="min-h-11 sm:min-h-9">
          Skip
        </Button>
      </div>
    </form>
  );
}
