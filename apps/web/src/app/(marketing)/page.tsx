import {
  ArrowRight,
  CircleHelp,
  Eye,
  FileSearch,
  Gauge,
  KeyRound,
  Languages,
  Lock,
  ShieldAlert,
  ShieldCheck,
  Timer,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { HeroScene } from "@/components/landing/hero-scene";
import { TrySandbox } from "@/components/landing/interactive";
import { Channels, ProductSteps, ProofCards, ReviewLoop } from "@/components/landing/sections";
import { InkSheet, SplitHead } from "@/components/landing/sheets";
import { TriageDemo } from "@/components/landing/triage-demo";
import { Reveal, ScrollReveal } from "@/components/motion";

export const metadata: Metadata = {
  title: { absolute: "ResolveIT · Ambiguity in. One calibrated path out." },
  description: "ResolveIT reads IT problems in the words people actually use, then routes, asks one question, or hands off to a person. Never a guess.",
};

const FEATURES = [
  { Icon: Languages, t: "Reads how people talk", d: "English, Hindi or Hinglish. Nobody has to name the system or fill in a form first." },
  { Icon: CircleHelp, t: "Asks before it guesses", d: "When several teams still fit, it asks one optional question instead of picking one." },
  { Icon: FileSearch, t: "Shows its evidence", d: "Every route points back to the exact words that decided it, so anyone can check it." },
  { Icon: ShieldAlert, t: "Escalates what matters", d: "A security signal skips every question and goes straight to a person." },
];

const TRUST = [
  { Icon: Lock, t: "Saved before analysed", d: "Encrypted and stored first. Nothing is lost." },
  { Icon: Eye, t: "Personal data masked", d: "Emails, phones and ID numbers hidden from the model." },
  { Icon: ShieldCheck, t: "No LLM decides", d: "Agents may propose. They never route." },
  { Icon: ShieldAlert, t: "Security escalates", d: "No questions. Straight to a person." },
  { Icon: KeyRound, t: "Keys stay on the server", d: "Your browser never holds an API key." },
  { Icon: Timer, t: "Shadow mode first", d: "Suggests only, until proven on your tickets." },
];

const FAQ = [
  ["Does it use ChatGPT or another LLM?", "No. Routing uses deterministic rules and a small model trained for this one task, checked by statistics. AI agents can file tickets, but they never make the routing decision."],
  ["What if it isn't sure?", "It asks one optional question, or it hands the ticket to a person and says why. It does not guess."],
  ["Which languages does it understand?", "English, Hindi and Hinglish today, including mixed scripts. Marathi and Tamil are next."],
  ["Will it route our real tickets on day one?", "No. A new workspace starts in shadow mode: it suggests, a person decides. It routes on its own only after passing a test on your own reviewed tickets."],
  ["Where do the numbers on this page come from?", "From 624 generated test tickets the model never saw, and from tickets sent to the live demo engine. None of it is a customer's data."],
  ["How do I try it?", "Use the demo and the preview on this page, browse the examples, or sign in with the key your admin gave you."],
] as const;

export default function LandingPage() {
  return (
    <div className="overflow-x-clip">
      {/* Hero */}
      <section aria-labelledby="hero-title" className="relative mx-auto grid max-w-6xl items-center gap-6 px-5 pb-10 pt-10 lg:grid-cols-[1.05fr_1fr] lg:pt-16">
        <Reveal>
          <p className="eyebrow inline-flex items-center gap-2">
            <span aria-hidden="true" className="h-px w-6 bg-signal" /> Incident intelligence for IT teams
          </p>
          <h1 id="hero-title" className="text-[clamp(2.75rem,7vw,5.25rem)] font-semibold leading-[0.95] tracking-[-0.055em]">
            Ambiguity in.
            <br />
            One <span className="text-signal">calibrated</span>
            <br />
            path out.
          </h1>
          <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted-foreground">
            ResolveIT reads IT problems in the words people actually use. Then it routes the ticket, asks one question, or hands it to a person.
            <span className="text-foreground"> Never a guess.</span>
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="#demo" className="workspace-button primary !min-h-12 !rounded-2xl !px-6 text-[15px]">
              Watch it work <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
            <Link href="/examples" className="workspace-button !min-h-12 !rounded-2xl !px-6 text-[15px]">
              See 30 real examples
            </Link>
          </div>
          <ul className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
            <li className="inline-flex items-center gap-2"><Languages aria-hidden="true" className="size-4 text-signal" /> English · <span lang="hi">हिन्दी</span> · Hinglish</li>
            <li className="inline-flex items-center gap-2"><ShieldCheck aria-hidden="true" className="size-4 text-signal" /> No LLM decides</li>
            <li className="inline-flex items-center gap-2"><Gauge aria-hidden="true" className="size-4 text-signal" /> 40 ms per decision</li>
          </ul>
        </Reveal>
        <HeroScene className="h-[340px] sm:h-[460px] lg:h-[560px]" />
      </section>


      {/* Demo */}
      <InkSheet id="demo" labelledBy="demo-title" className="mt-6">
        <SplitHead
          id="demo-title"
          eyebrow="Watch it work"
          title="Watch it triage a ticket."
          sub="Pick a real report. It passes through five layers in under a second, then goes to a team, asks one question, or reaches a person. Every number here came from the live engine."
        />
        <div className="mt-12">
          <TriageDemo />
        </div>
        <div className="mt-24 border-t pt-16 sm:mt-28">
          <SplitHead
            id="why"
            title="Most tickets start as a guess. These don't."
            sub="People describe problems, not systems. A wrong guess sends a ticket to the wrong queue, and nobody can see why. ResolveIT reads first, decides only when it can prove it, and shows its working."
          />
          <ul className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map(({ Icon, t, d }, i) => (
              <ScrollReveal as="li" key={t} delay={i * 0.06} className="rounded-2xl border bg-card p-6">
                <Icon aria-hidden="true" className="size-5 text-signal" />
                <h3 className="mt-6 text-lg font-semibold tracking-[-0.02em]">{t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{d}</p>
              </ScrollReveal>
            ))}
          </ul>
        </div>
      </InkSheet>

      {/* Try it */}
      <section id="try" aria-labelledby="try-title" className="mx-auto max-w-6xl scroll-mt-24 px-5 pt-24 sm:pt-32">
        <SplitHead id="try-title" eyebrow="Try it" title="Now type your own." sub="Write a problem the way a colleague would. The same rules the engine uses show what they can read, right in your browser." />
        <ScrollReveal className="mt-12">
          <TrySandbox />
        </ScrollReveal>
      </section>

      {/* Proof */}
      <section id="proof" aria-labelledby="proof-title" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-24 sm:py-32">
        <SplitHead id="proof-title" eyebrow="Proof" title="Proven before it's trusted.">
          <p>
            Results on 624 generated tickets the model had never seen. They show the system works as designed; they are not a measure on a customer&apos;s tickets.{" "}
            <Link href="/dataset" className="font-semibold text-signal underline underline-offset-4">How it was tested</Link>
          </p>
        </SplitHead>
        <div className="mt-12">
          <ProofCards />
        </div>
      </section>

      {/* Product */}
      <InkSheet id="product" labelledBy="product-title">
        <SplitHead
          id="product-title"
          eyebrow="The product"
          title="From one sentence to the right queue."
          sub="One workspace for everyone who touches a ticket: the person reporting it, the people reviewing it, and the team proving it is safe."
        />
        <div className="mt-14">
          <ProductSteps />
        </div>
        <p className="mt-10 text-sm text-muted-foreground">
          Also in the workspace:{" "}
          <Link href="/mcp" className="font-semibold text-foreground underline underline-offset-4">agent hand-off</Link> and{" "}
          <Link href="/settings" className="font-semibold text-foreground underline underline-offset-4">queue settings</Link>.
        </p>
      </InkSheet>

      {/* Loop */}
      <section aria-labelledby="loop-title" className="mx-auto max-w-6xl px-5 py-24 sm:py-32">
        <SplitHead
          id="loop-title"
          eyebrow="Shadow mode"
          title="Every review makes it safer."
          sub="A new workspace only suggests. Each ticket your people decide becomes a reviewed example, and those examples are the test it must pass before it routes on its own."
        />
        <div className="mt-14">
          <ReviewLoop />
        </div>
      </section>

      {/* Channels + trust */}
      <InkSheet id="channels" labelledBy="channels-title">
        <SplitHead id="channels-title" eyebrow="Built in" title="However the ticket arrives." sub="People, AI agents and your own systems all reach the same engine and get the same decision.">
          <Link href="/architecture" className="mt-4 flex w-fit items-center gap-1.5 text-base font-semibold text-signal underline underline-offset-4">
            See the architecture <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </SplitHead>
        <div className="mt-12">
          <Channels />
        </div>
        <ul className="mt-16 grid grid-cols-1 gap-x-10 gap-y-8 border-t pt-12 sm:grid-cols-2 lg:grid-cols-3">
          {TRUST.map(({ Icon, t, d }, i) => (
            <ScrollReveal as="li" key={t} delay={(i % 3) * 0.05} className="flex items-start gap-4">
              <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-signal" />
              <span>
                <span className="block font-semibold">{t}</span>
                <span className="mt-1 block text-sm text-muted-foreground">{d}</span>
              </span>
            </ScrollReveal>
          ))}
        </ul>
      </InkSheet>

      {/* FAQ */}
      <section aria-labelledby="faq" className="mx-auto grid max-w-6xl gap-10 px-5 py-24 sm:py-32 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
        <ScrollReveal>
          <h2 id="faq" className="text-[clamp(2.1rem,4.6vw,3.6rem)] font-semibold leading-[1.02] tracking-[-0.045em]">
            Questions teams ask first.
          </h2>
          <p className="mt-4 text-muted-foreground">
            Anything else is in the <Link href="/docs" className="font-semibold text-signal underline underline-offset-4">docs</Link>.
          </p>
        </ScrollReveal>
        <div className="divide-y border-y">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group py-5 [&_summary::-webkit-details-marker]:hidden">
              <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 text-lg font-semibold">
                {q}
                <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full border text-muted-foreground transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="mt-2 pr-10 leading-relaxed text-muted-foreground">{a}</p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
