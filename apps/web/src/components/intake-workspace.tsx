"use client";

import { useMemo, useRef, useState } from "react";

import { DetailMeter } from "@/components/detail-meter";
import { IncidentPanel } from "@/components/incident/incident-panel";
import { SyntheticBanner } from "@/components/synthetic-banner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { measure } from "@/lib/meter";
import type { IncidentView, Locale } from "@/lib/types";

const LOCALES: { value: Locale; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "hinglish", label: "Hinglish" },
];
const MAX = 20_000;

async function send(url: string, body: unknown): Promise<IncidentView> {
  const res = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(res.status === 409 ? "This question was already closed." : `The service returned ${res.status}.`);
  return (await res.json()) as IncidentView;
}

export function IntakeWorkspace() {
  const [text, setText] = useState("");
  const [locale, setLocale] = useState<Locale>("en");
  const [view, setView] = useState<IncidentView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const meter = useMemo(() => measure(text), [text]);

  const run = async (action: () => Promise<IncidentView>) => {
    setBusy(true);
    setError(null);
    try {
      setView(await action());
      requestAnimationFrame(() => resultRef.current?.querySelector<HTMLElement>("[data-result-heading]")?.focus());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const trimmed = text.trim();
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <form
        className="space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          if (trimmed) void run(() => send("/api/incidents", { text, locale, channel: "web" }));
        }}
      >
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Report a problem</h1>
          <p className="mt-1 text-sm text-muted-foreground">Write it the way you would say it. English, Hindi or a mix.</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="problem">What is going wrong?</Label>
          <Textarea
            id="problem"
            value={text}
            maxLength={MAX}
            rows={7}
            onChange={(e) => setText(e.target.value)}
            placeholder="VPN keeps dropping since this morning for the whole floor"
            aria-describedby="problem-help"
            className="min-h-40 bg-card text-base"
          />
          <p id="problem-help" className="text-xs text-muted-foreground">
            Paste any error code exactly as shown. Phone numbers and IDs are masked before storage.
          </p>
        </div>
        <fieldset>
          <legend className="text-sm font-medium">Language for any follow-up question</legend>
          <div className="mt-2 inline-flex rounded-md border bg-card p-0.5">
            {LOCALES.map((option) => (
              <label
                key={option.value}
                className="inline-flex min-h-11 cursor-pointer items-center rounded-sm px-3 text-sm has-checked:bg-secondary has-checked:font-medium has-focus-visible:outline-2 has-focus-visible:outline-ring sm:min-h-8"
              >
                <input
                  type="radio"
                  name="locale"
                  value={option.value}
                  checked={locale === option.value}
                  onChange={() => setLocale(option.value)}
                  className="sr-only"
                />
                <span lang={option.value === "hi" ? "hi" : "en"}>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <DetailMeter result={meter} />
        {meter.security ? (
          <p role="status" className="rounded-md bg-risk-surface px-3 py-2 text-sm text-risk">
            This reads like a security incident. Send it now; the Security team is flagged straight away.
          </p>
        ) : null}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={busy || !trimmed} className="min-h-11 px-5 sm:min-h-9">
            {busy ? "Sending…" : "Send ticket"}
          </Button>
          {error ? <p role="alert" className="text-sm text-risk">{error} Your text is still here; try again.</p> : null}
        </div>
      </form>

      <section aria-label="Result" aria-live="polite" ref={resultRef} className="space-y-4">
        {view?.is_synthetic_tenant ? <SyntheticBanner /> : null}
        {view ? (
          <IncidentPanel
            view={view}
            busy={busy}
            onAnswer={(answer) => void run(() => send(`/api/incidents/${view.id}/answer`, { answer }))}
          />
        ) : (
          <Card>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p className="text-base font-medium text-foreground">What happens when you send</p>
              <ol className="list-decimal space-y-1 pl-5">
                <li>The ticket is saved first, so nothing is lost.</li>
                <li>You see which details were understood, marked in your own words.</li>
                <li>It goes to a team, or to a person if the team is not clear. You may get one optional question.</li>
              </ol>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}
