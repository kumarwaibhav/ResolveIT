import { Cloud, Cpu, Database, Globe2, Server } from "lucide-react";
import type { Metadata } from "next";

import { PageHero } from "@/components/landing/page-hero";
import Link from "next/link";

import { DecisionEngine, RequestLifecycle, SecurityLayers, SystemMap } from "@/components/architecture/diagrams";
import { GlassCard, ScrollReveal } from "@/components/motion";

export const metadata: Metadata = { title: "Architecture" };

function Head({ n, title, sub, id }: { n: string; title: string; sub: string; id: string }) {
  return (
    <ScrollReveal className="mb-8 max-w-2xl">
      <p className="eyebrow">{n}</p>
      <h2 id={id} className="text-[clamp(1.75rem,3.6vw,2.5rem)] font-bold leading-tight tracking-[-0.04em]">{title}</h2>
      <p className="mt-2 text-muted-foreground">{sub}</p>
    </ScrollReveal>
  );
}

const DEPLOY = [
  { Icon: Globe2, t: "Web app", where: "Vercel · Mumbai (bom1)", d: "Static pages at the edge; server functions next to India." },
  { Icon: Server, t: "Decision API", where: "Modal · Asia routing", d: "Scales to zero when idle; wakes on the first request." },
  { Icon: Database, t: "Database", where: "Neon · Singapore", d: "Managed Postgres 16 with row-level security." },
  { Icon: Cpu, t: "Model", where: "Inside the API container", d: "INT8 on CPU. No GPU and no third-party AI service." },
];

const TOC = [
  ["map", "System map"],
  ["lifecycle", "One request"],
  ["engine", "Decision engine"],
  ["security", "Security layers"],
  ["deploy", "Deployment"],
] as const;

export default function ArchitecturePage() {
  return (
    <>
      <PageHero
        eyebrow="Architecture"
        title="Four parts. One path."
        sub="How a ticket travels, where every decision is made, and the walls that keep each customer's data apart."
        stats={[
          { label: "Decision path", value: "Rules + one encoder" },
          { label: "LLMs in the decision", value: "None" },
          { label: "Median decision", value: "40 ms on CPU" },
          { label: "Model", value: "315 MB · signed bundle" },
        ]}
      />
    <div className="mx-auto max-w-6xl px-5 pt-12">
      <nav aria-label="On this page" className="mt-8 flex gap-2 overflow-x-auto pb-1">
        {TOC.map(([id, label], i) => (
          <a key={id} href={`#${id}`} className="glass shrink-0 rounded-full px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground">
            <span className="mr-1.5 font-mono text-xs">{String(i + 1).padStart(2, "0")}</span>
            {label}
          </a>
        ))}
      </nav>

      <div className="mt-16 space-y-24">
        <section id="map" aria-labelledby="h-map" className="scroll-mt-24">
          <Head n="01 · System map" id="h-map" title="Who talks to whom." sub="Select any part to see its job. The moving dots trace live traffic." />
          <SystemMap />
        </section>

        <section id="lifecycle" aria-labelledby="h-life" className="scroll-mt-24">
          <Head n="02 · One request" id="h-life" title="The life of a ticket." sub="Eight steps from send to answer. Typically about one second end to end." />
          <RequestLifecycle />
        </section>

        <section id="engine" aria-labelledby="h-engine" className="scroll-mt-24">
          <Head n="03 · Decision engine" id="h-engine" title="Six checks before any route." sub="Each step narrows the answer. If the last check fails, a person decides." />
          <DecisionEngine />
        </section>

        <section id="security" aria-labelledby="h-sec" className="scroll-mt-24">
          <Head n="04 · Security layers" id="h-sec" title="Defence in depth." sub="Six independent layers between the internet and a customer's data." />
          <SecurityLayers />
        </section>

        <section id="deploy" aria-labelledby="h-deploy" className="scroll-mt-24">
          <Head n="05 · Deployment" id="h-deploy" title="Where it runs." sub="Close to users in India, on infrastructure that costs nothing when idle." />
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {DEPLOY.map(({ Icon, t, where, d }, i) => (
              <ScrollReveal as="li" key={t} delay={i * 0.06} className="h-full">
                  <GlassCard tilt className="h-full p-6">
                    <Icon aria-hidden="true" className="size-6 text-signal" />
                    <h3 className="mt-5 text-lg font-bold">{t}</h3>
                    <p className="text-sm font-medium">{where}</p>
                    <p className="mt-2 text-sm text-muted-foreground">{d}</p>
                  </GlassCard>
                </ScrollReveal>
            ))}
          </ul>
          <p className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
            <Cloud aria-hidden="true" className="size-4" /> Want the endpoints? Read the <Link href="/docs/api" className="font-semibold text-signal underline underline-offset-4">API reference</Link>.
          </p>
        </section>
      </div>
    </div>
    </>
  );
}
