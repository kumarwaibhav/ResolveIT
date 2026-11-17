"use client";

import { ArrowUp, Bot, Languages, ListChecks, MessageCircleQuestion, ShieldAlert, Sparkles } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useMemo, useRef, useState } from "react";

import { DetailMeter } from "@/components/detail-meter";
import { IncidentPanel } from "@/components/incident/incident-panel";
import { GlassCard, Reveal } from "@/components/motion";
import { SyntheticBanner } from "@/components/synthetic-banner";
import { Button } from "@/components/ui/button";
import { PipelineProgress, PipelineTrack } from "@/components/viz/pipeline";
import { WorkspaceHeading } from "@/components/workspace-heading";
import { measure } from "@/lib/meter";
import { cn } from "@/lib/utils";
import type { IncidentView, Locale } from "@/lib/types";

const LOCALES: { value: Locale; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "hinglish", label: "Hinglish" },
];
const MAX = 20_000;

/** The four canonical demo tickets (docs/DEMO_WALKTHROUGH.md). Filling the box sends nothing. */
const EXAMPLES = [
  { label: "Clear", text: "Outlook keeps crashing for the whole floor since this morning" },
  { label: "Vague · Hinglish", text: "kal se kuch bhi kaam nahi kar raha, please jaldi dekho" },
  { label: "Two problems", text: "VPN disconnects every few minutes and after that MS Teams calls drop, whole team since yesterday" },
  { label: "Security", text: "I clicked a link in an email and typed my password, now my account is sending spam to everyone" },
];

const FACTS = [
  { Icon: ListChecks, value: "11", label: "details read from every report" },
  { Icon: Languages, value: "3", label: "languages, mixed freely" },
  { Icon: MessageCircleQuestion, value: "≤ 1", label: "optional question, never more" },
  { Icon: Bot, value: "0", label: "LLMs in the routing decision" },
];

async function send(url: string, body: unknown): Promise<IncidentView> {
  const res = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(res.status === 409 ? "This question was already closed." : `The service returned ${res.status}.`);
  return (await res.json()) as IncidentView;
}

export function IntakeWorkspace() {
  const [text, setText] = useState("");
  const [locale, setLocale] = useState<Locale>("en");
  const [view, setView] = useState<IncidentView | null>(null);
  const [pending, setPending] = useState<"new" | "answer" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resultRef = useRef<HTMLElement>(null);
  const meter = useMemo(() => measure(text), [text]);
  const reduce = useReducedMotion();
  const busy = pending !== null;

  const run = async (kind: "new" | "answer", action: () => Promise<IncidentView>) => {
    setPending(kind);
    setError(null);
    try {
      setView(await action());
      requestAnimationFrame(() => resultRef.current?.querySelector<HTMLElement>("[data-result-heading]")?.focus());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setPending(null);
    }
  };

  const trimmed = text.trim();
  return (
    <div>
      <WorkspaceHeading
        eyebrow="01 · Incident intake"
        title="Describe it. We'll take it from there."
        description="Write the problem in your own words. You see exactly what was understood, then it goes to the right team, gets one optional question, or reaches a person."
      >
        <span className="pill-status">Human oversight on</span>
      </WorkspaceHeading>

      <ul className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {FACTS.map(({ Icon, value, label }, i) => (
          <Reveal key={label} as="li" delay={i * 0.03}>
            <GlassCard tilt className="flex h-full items-center gap-3 p-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent text-signal" aria-hidden="true">
                <Icon className="size-5" />
              </span>
              <span className="min-w-0">
                <span className="block text-2xl font-bold tracking-[-0.04em] tabular">{value}</span>
                <span className="block text-xs leading-snug text-muted-foreground">{label}</span>
              </span>
            </GlassCard>
          </Reveal>
        ))}
      </ul>

      <div className="grid items-start gap-6 xl:grid-cols-2">
        <GlassCard className="p-5 sm:p-6">
          <form
            className="space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              if (trimmed) void run("new", () => send("/api/incidents", { text, locale, channel: "web" }));
            }}
          >
            <div>
              <h2 className="text-xl font-bold tracking-[-0.03em]">Report a problem</h2>
              <p className="mt-1 text-sm text-muted-foreground">Write it the way you would say it out loud.</p>
            </div>

            <div className="space-y-2">
              <label htmlFor="problem" className="text-sm font-semibold">What is going wrong?</label>
              <div className="relative rounded-2xl border bg-card transition-shadow focus-within:border-ring focus-within:shadow-[0_0_0_4px_var(--glow)]">
                <textarea
                  id="problem"
                  value={text}
                  maxLength={MAX}
                  rows={6}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="VPN keeps dropping since this morning for the whole floor"
                  aria-describedby="problem-help"
                  className="block min-h-40 w-full resize-y rounded-2xl bg-transparent px-4 pb-12 pt-3.5 text-base leading-relaxed outline-none placeholder:text-muted-foreground"
                />
                <span className="pointer-events-none absolute bottom-3 left-4 font-mono text-[11px] text-muted-foreground tabular" aria-hidden="true">
                  {text.length.toLocaleString("en-IN")} / 20,000
                </span>
              </div>
              <p id="problem-help" className="text-xs leading-relaxed text-muted-foreground">
                Paste error codes exactly as shown. Personal identifiers are masked before analysis, and your original report is encrypted.
              </p>
            </div>

            <div>
              <p className="mono-label mb-2 inline-flex items-center gap-1.5">
                <Sparkles aria-hidden="true" className="size-3" /> Try an example
              </p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex.label}
                    type="button"
                    onClick={() => setText(ex.text)}
                    className="min-h-9 rounded-full border bg-card px-3 text-xs font-medium text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
            </div>

            <fieldset>
              <legend className="text-sm font-semibold">Language for any follow-up question</legend>
              <div className="relative mt-2 inline-flex rounded-xl border bg-card p-1">
                {LOCALES.map((option) => {
                  const on = locale === option.value;
                  return (
                    <label key={option.value} className="relative inline-flex min-h-11 cursor-pointer items-center rounded-lg px-4 text-sm font-medium has-focus-visible:outline-2 has-focus-visible:outline-ring">
                      {on ? (
                        <motion.span
                          layoutId="locale-pill"
                          className="absolute inset-0 rounded-lg bg-foreground"
                          transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 500, damping: 36 }}
                        />
                      ) : null}
                      <input type="radio" name="locale" value={option.value} checked={on} onChange={() => setLocale(option.value)} className="sr-only" />
                      <span lang={option.value === "hi" ? "hi" : "en"} className={cn("relative", on ? "text-background" : "text-muted-foreground")}>
                        {option.label}
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>

            <DetailMeter result={meter} />

            <AnimatePresence>
              {meter.security ? (
                <motion.p
                  role="status"
                  initial={reduce ? false : { opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex items-start gap-2.5 overflow-hidden rounded-2xl border border-risk/30 bg-risk-surface px-4 py-3 text-sm text-risk"
                >
                  <ShieldAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                  This reads like a security incident. Send it now; the Security team is flagged straight away.
                </motion.p>
              ) : null}
            </AnimatePresence>

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={busy || !trimmed} className="min-h-12 gap-2 rounded-2xl px-6 text-[15px]">
                {pending === "new" ? "Sending…" : "Send ticket"}
                <ArrowUp aria-hidden="true" className="size-4" />
              </Button>
              {error ? (
                <p role="alert" className="text-sm text-risk">
                  {error} Your text is still here; try again.
                </p>
              ) : null}
            </div>
          </form>
        </GlassCard>

        <section aria-label="Result" aria-live="polite" ref={resultRef} className="space-y-4 xl:sticky xl:top-24">
          {view?.is_synthetic_tenant ? <SyntheticBanner /> : null}
          {pending === "new" ? (
            <PipelineProgress />
          ) : view ? (
            <IncidentPanel view={view} busy={busy} onAnswer={(answer) => void run("answer", () => send(`/api/incidents/${view.id}/answer`, { answer }))} />
          ) : (
            <div className="glass relative overflow-hidden rounded-2xl border-dashed p-6 sm:p-8">
              <p className="eyebrow">Evidence, then action</p>
              <h2 className="text-2xl font-bold tracking-[-0.03em]">A little context goes a long way.</h2>
              <p className="mt-2 text-sm text-muted-foreground">What was understood, and why, will appear here.</p>
              <div className="my-8">
                <PipelineTrack active={-1} />
              </div>
              <h3 className="text-sm font-semibold">What happens when you send</h3>
              <ol className="mt-3 space-y-3">
                {[
                  "The ticket is saved first, so nothing is lost.",
                  "You see which details were understood, marked in your own words.",
                  "It goes to a team, or to a person if the team is not clear. You may get one optional question.",
                ].map((step, i) => (
                  <li key={step} className="flex items-start gap-3 text-sm text-muted-foreground">
                    <span className="grid size-6 shrink-0 place-items-center rounded-full border bg-card font-mono text-[11px] font-semibold text-foreground">{i + 1}</span>
                    <span className="pt-0.5">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
