import { AlertTriangle, Binary, Cpu, FileLock2, Gauge, Languages, Layers3, Mic, Sparkles, Timer } from "lucide-react";
import type { Metadata } from "next";

import { GlassCard, NumberTicker, Reveal } from "@/components/motion";
import { Donut, StackedBar } from "@/components/viz/charts";
import { WorkspaceHeading } from "@/components/workspace-heading";

export const metadata: Metadata = { title: "Data & model" };

/* Every figure below is copied from training/data_free.py (PLAN × 12 teams) and the release bundle
   report recorded in docs/BUILD_STATE.md. Nothing here is estimated. */
const SPLITS = [
  { label: "Head training", value: 1800, note: "Fits the small decision head on top of the encoder" },
  { label: "Temperature scaling", value: 360, note: "Makes probabilities honest" },
  { label: "Conformal calibration", value: 2040, note: "Sizes the plausible-team sets" },
  { label: "Risk certification", value: 3360, note: "Proves the ≤ 5% misroute bound per queue" },
  { label: "Answer certification", value: 3840, note: "Checks routing after one answered question" },
  { label: "Policy selection", value: 120, note: "Chooses between candidate policies" },
  { label: "Frozen test", value: 600, note: "Never seen until the final evaluation" },
];

const OUTCOMES = [
  { label: "Routed straight away", value: 455, note: "455 of 455 correct · 0 misroutes" },
  { label: "Asked one question", value: 160, note: "111 answered, then routed; every one correct" },
  { label: "Handed to a person", value: 9, note: "Deferred with a stated reason" },
];

const KINDS = [
  { label: "Clear", value: 75, note: "Names a system the rules recognise, so the team is identifiable" },
  { label: "Vague", value: 25, note: "No system named; only a question can recover the team" },
];

const MODEL = [
  { Icon: Layers3, k: "Encoder", v: "mDeBERTa-v3 base", d: "Multilingual transformer, fine-tuned with LoRA" },
  { Icon: Binary, k: "Weights", v: "INT8 · 315 MB", d: "Down from 867 MB FP32, block-32 quantised" },
  { Icon: Gauge, k: "Fidelity", v: "0.9999 cosine", d: "INT8 vs FP32 pooled output" },
  { Icon: Timer, k: "Pipeline", v: "40 ms p50", d: "Typical short ticket, 4 CPU threads" },
  { Icon: Cpu, k: "Long input", v: "177 ms p50", d: "128 tokens; target is 50 ms" },
  { Icon: FileLock2, k: "Bundle", v: "SHA-256 pinned", d: "Model, thresholds and costs verified on load" },
];

export default function DatasetPage() {
  return (
    <div className="space-y-6">
      <WorkspaceHeading
        eyebrow="Learn · Data & model"
        title="What it learned from, and what it proved."
        description="The model was trained and calibrated on generated tickets in English, Hindi and Hinglish. Here is exactly what that data looks like, how it was split, and how the shipped model performed on tickets it never saw."
      />

      <p role="note" className="flex items-start gap-3 rounded-2xl border border-warn/30 bg-warn-surface px-4 py-3 text-sm leading-relaxed text-warn">
        <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>
          <strong className="font-semibold">All data on this page is synthetic.</strong> Results show the system works as designed; they are not a measure of accuracy on any
          customer&apos;s tickets. Labels are recorded as <code className="font-mono">synthetic_seed</code> and production routing stays switched off for real tenants.
        </span>
      </p>

      <ul className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {[
          { v: 12120, l: "generated tickets for fitting and testing" },
          { v: 792, l: "seed rows used to fine-tune the encoder" },
          { v: 624, l: "frozen test tickets" },
          { v: 12, l: "teams a ticket can route to" },
          { v: 3, l: "languages: en · hi · Hinglish" },
        ].map((x, i) => (
          <Reveal key={x.l} as="li" delay={i * 0.02} className={i === 0 ? "col-span-2 lg:col-span-1" : undefined}>
            <GlassCard tilt className="h-full p-5">
              <span className="block text-3xl font-bold tracking-[-0.04em]">
                <NumberTicker value={x.v} />
              </span>
              <span className="mt-1 block text-xs leading-snug text-muted-foreground">{x.l}</span>
            </GlassCard>
          </Reveal>
        ))}
      </ul>

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <section className="surface-panel" aria-labelledby="splits">
          <p className="eyebrow">Seven disjoint splits</p>
          <h2 id="splits" className="panel-title">Every job gets its own data</h2>
          <p className="panel-copy mb-6">No ticket appears in two splits, so each step is checked on data it was not fitted on. Counts are 12 teams × the per-team plan.</p>
          <StackedBar segments={SPLITS} caption="Generated tickets by split" />
        </section>
        <section className="surface-panel" aria-labelledby="kinds">
          <p className="eyebrow">What a ticket looks like</p>
          <h2 id="kinds" className="panel-title">Clear, vague, and security</h2>
          <p className="panel-copy mb-6">
            A quarter of each split is deliberately vague: the team cannot be read from the text. That is what teaches the system when to ask instead of guess. Security
            tickets describe phishing or a compromised account without naming a system.
          </p>
          <StackedBar compact segments={KINDS} caption="Share of clear and vague tickets in most splits (percent)" />
          <ul className="mt-6 space-y-2 text-sm">
            <li className="flex items-start gap-2"><Languages aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-signal" /> Phrases in English, Devanagari Hindi and romanised Hinglish.</li>
            <li className="flex items-start gap-2"><Sparkles aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-signal" /> A unique tag per row: no text repeats across splits.</li>
          </ul>
        </section>
      </div>

      <section className="surface-panel" aria-labelledby="results">
        <div className="grid gap-8 lg:grid-cols-[1.2fr_1fr] lg:items-center">
          <div>
            <p className="eyebrow">Frozen synthetic test · 624 tickets</p>
            <h2 id="results" className="panel-title">It routes when it is sure, asks when it is not</h2>
            <p className="panel-copy">
              On tickets it had never seen, the shipped INT8 model routed 455 directly with no mistakes, asked one question on 160 and handed 9 to a person. Overall, 90.7%
              reached the right team without a human, and the plausible-team sets contained the right team 92.3% of the time (target 90%).
            </p>
            <p className="mt-3 text-xs text-muted-foreground">
              Caveat: generated tickets share templates, so this proves the mechanism, not real-world accuracy. Vague tickets carry random labels by construction.
            </p>
          </div>
          <Donut segments={OUTCOMES} centre="624" sub="test tickets" />
        </div>
      </section>

      <section aria-labelledby="model">
        <p className="eyebrow">Model card</p>
        <h2 id="model" className="mb-5 text-2xl font-bold tracking-[-0.03em]">Small, fast and verifiable</h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {MODEL.map(({ Icon, k, v, d }, i) => (
            <Reveal key={k} as="li" delay={i * 0.02}>
              <GlassCard tilt className="flex h-full items-start gap-4 p-5">
                <span aria-hidden="true" className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent text-signal">
                  <Icon className="size-5" />
                </span>
                <span>
                  <span className="mono-label block">{k}</span>
                  <span className="mt-1 block text-lg font-bold tracking-[-0.02em]">{v}</span>
                  <span className="block text-xs text-muted-foreground">{d}</span>
                </span>
              </GlassCard>
            </Reveal>
          ))}
        </ul>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="surface-panel" aria-labelledby="governance">
          <p className="eyebrow">Governance</p>
          <h2 id="governance" className="panel-title">Rules the data cannot bend</h2>
          <ul className="mt-3 space-y-3 text-sm">
            {[
              "Thresholds are fitted on the exact INT8 model that ships, never on a different build.",
              "Risk certificates use a 5% misroute bound at 95% confidence, corrected for 12 queues.",
              "Synthetic labels can never be exported as human gold.",
              "A real tenant routes on its own only after reviewed tickets from that tenant pass the frozen test.",
            ].map((t) => (
              <li key={t} className="flex items-start gap-3">
                <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-signal" />
                <span className="text-muted-foreground">{t}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="surface-panel" aria-labelledby="roadmap">
          <p className="eyebrow">Next</p>
          <h2 id="roadmap" className="panel-title">Training v2</h2>
          <ul className="mt-3 space-y-3 text-sm">
            {[
              { Icon: Languages, t: "Marathi and Tamil, with more varied phrasing" },
              { Icon: Cpu, t: "A distilled student model to reach 50 ms on 128 tokens" },
              { Icon: Mic, t: "Voice intake: phone call → transcript → ticket, outside the decision path" },
            ].map(({ Icon, t }) => (
              <li key={t} className="flex items-start gap-3">
                <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-signal" />
                <span className="text-muted-foreground">{t}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
