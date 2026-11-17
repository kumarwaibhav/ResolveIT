import {
  ArrowRight,
  Bot,
  CircleHelp,
  Eye,
  FlaskConical,
  Gauge,
  Inbox,
  KeyRound,
  Languages,
  Lock,
  Route,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  Timer,
  UserRound,
  UsersRound,
  Waypoints,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { HeroScene } from "@/components/landing/hero-scene";
import { HowItWorks, TrySandbox } from "@/components/landing/interactive";
import { GlassCard, NumberTicker, Reveal, ScrollReveal } from "@/components/motion";

export const metadata: Metadata = {
  title: { absolute: "ResolveIT · Ambiguity in. One calibrated path out." },
  description: "ResolveIT reads IT problems in the words people actually use, then routes, asks one question, or hands off to a person. Never a guess.",
};

function SectionHead({ eyebrow, title, sub, id }: { eyebrow: string; title: string; sub?: string; id: string }) {
  return (
    <ScrollReveal className="mx-auto max-w-3xl text-center">
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={id} className="text-gradient text-[clamp(2rem,4.6vw,3.5rem)] font-bold leading-[1.04] tracking-[-0.045em]">
        {title}
      </h2>
      {sub ? <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">{sub}</p> : null}
    </ScrollReveal>
  );
}

const PROBLEMS = [
  { n: "01", t: "People don't speak in ticket fields.", d: "Reports arrive as “nothing works since yesterday”. The system is rarely named." },
  { n: "02", t: "A wrong guess costs hours.", d: "The ticket waits in the wrong queue, gets passed on, and waits again." },
  { n: "03", t: "Black boxes don't earn trust.", d: "If no one can see why a ticket went somewhere, no one can fix it." },
];

const OUTCOMES = [
  { Icon: Route, verb: "Route", when: "When it is sure.", eg: "“Outlook keeps crashing for the whole floor”", to: "Email & Collaboration", tone: "bg-primary text-primary-foreground" },
  { Icon: CircleHelp, verb: "Ask", when: "When one answer settles it.", eg: "“kal se kuch bhi kaam nahi kar raha”", to: "“Which system or app is this about?”", tone: "bg-info-surface text-info" },
  { Icon: UserRound, verb: "Hand off", when: "When it matters too much to guess.", eg: "“I clicked a link and typed my password”", to: "A person, flagged for Security", tone: "bg-risk-surface text-risk" },
];

const PROOF = [
  { v: 455, suffix: "", pre: "", of: "/ 455", l: "Auto-routed tickets correct", n: "Zero misroutes", big: true },
  { v: 90.7, d: 1, suffix: "%", l: "Reached the right team without a person", n: "Including after one answer" },
  { v: 92.3, d: 1, suffix: "%", l: "Right team inside the plausible set", n: "Target was 90%" },
  { v: 40, suffix: " ms", l: "Median decision time", n: "Typical ticket, on CPU" },
  { v: 315, suffix: " MB", l: "Whole model on disk", n: "INT8, verified by hash" },
  { v: 0, suffix: "", l: "LLMs in the routing decision", n: "Rules + calibrated encoder" },
];

const ROOMS = [
  { Icon: Inbox, t: "Report a problem", d: "Type it as you'd say it. See what was understood.", href: "/intake" },
  { Icon: UsersRound, t: "Review", d: "Two people label blind. Agreement is measured.", href: "/review" },
  { Icon: Waypoints, t: "Bounce analyzer", d: "See where tickets get passed around.", href: "/bounce" },
  { Icon: FlaskConical, t: "Evaluation", d: "What the model has proved, and on what.", href: "/evaluation" },
  { Icon: Bot, t: "Agent hand-off", d: "Let AI agents file tickets, with receipts.", href: "/mcp" },
  { Icon: Settings2, t: "Settings", d: "Map teams to queues. Handle privacy requests.", href: "/settings" },
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
  ["How do I try it?", "Use the live preview on this page, browse the examples, or sign in with the key your admin gave you."],
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
          <h1 id="hero-title" className="text-gradient text-[clamp(2.75rem,7vw,5.25rem)] font-bold leading-[0.95] tracking-[-0.055em]">
            Ambiguity in.
            <br />
            One <span className="text-signal [-webkit-text-fill-color:var(--signal)]">calibrated</span>
            <br />
            path out.
          </h1>
          <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted-foreground">
            ResolveIT reads IT problems in the words people actually use. Then it routes the ticket, asks one question, or hands it to a person.
            <span className="text-foreground"> Never a guess.</span>
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="#try" className="workspace-button primary !min-h-12 !rounded-2xl !px-6 text-[15px]">
              Try it live <ArrowRight aria-hidden="true" className="size-4" />
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

      {/* Problem */}
      <section aria-labelledby="problem" className="mx-auto max-w-6xl px-5 py-20 sm:py-28">
        <SectionHead id="problem" eyebrow="The problem" title="Most tickets start as a guess." />
        <ol className="mt-14 grid gap-4 md:grid-cols-3">
          {PROBLEMS.map((p, i) => (
            <ScrollReveal as="li" key={p.n} delay={i * 0.08} className="glass h-full  rounded-3xl p-7">
                <span className="font-mono text-sm text-signal">{p.n}</span>
                <h3 className="mt-6 text-xl font-bold tracking-[-0.03em]">{p.t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{p.d}</p>
              </ScrollReveal>
          ))}
        </ol>
      </section>

      {/* Try it */}
      <section id="try" aria-labelledby="try-title" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-20">
        <SectionHead id="try-title" eyebrow="Try it now" title="Watch it read." sub="Type a problem the way a colleague would. See what it picks up, instantly." />
        <ScrollReveal className="mt-12">
          <TrySandbox />
        </ScrollReveal>
      </section>

      {/* How it works */}
      <section id="how" aria-labelledby="how-title" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-20 sm:py-28">
        <SectionHead id="how-title" eyebrow="How it works" title="Five steps. Under a second." sub="Every ticket takes the same path, so every decision can be explained." />
        <div className="mt-14">
          <HowItWorks />
        </div>
      </section>

      {/* Outcomes */}
      <section aria-labelledby="outcomes" className="mx-auto max-w-6xl px-5 py-20">
        <SectionHead id="outcomes" eyebrow="Three outcomes" title="Sure. Not sure. Too important." />
        <div className="mt-14 grid gap-4 lg:grid-cols-3">
          {OUTCOMES.map(({ Icon, verb, when, eg, to, tone }, i) => (
            <ScrollReveal key={verb} delay={i * 0.08}>
              <GlassCard tilt className="flex h-full flex-col p-7">
                <span aria-hidden="true" className={`grid size-12 place-items-center rounded-2xl ${tone}`}>
                  <Icon className="size-6" />
                </span>
                <h3 className="mt-6 text-3xl font-bold tracking-[-0.04em]">{verb}</h3>
                <p className="mt-1 text-muted-foreground">{when}</p>
                <div className="mt-auto pt-8">
                  <p className="rounded-2xl border bg-card px-4 py-3 text-sm">{eg}</p>
                  <p className="mt-2 flex items-center gap-2 px-1 text-sm font-semibold">
                    <ArrowRight aria-hidden="true" className="size-4 text-signal" /> {to}
                  </p>
                </div>
              </GlassCard>
            </ScrollReveal>
          ))}
        </div>
      </section>

      {/* Proof */}
      <section id="proof" aria-labelledby="proof-title" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-20 sm:py-28">
        <SectionHead id="proof-title" eyebrow="Proof" title="Proven before it's trusted." sub="Results on 624 tickets the model had never seen." />
        <ul className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PROOF.map((p, i) => (
            <ScrollReveal as="li" key={p.l} delay={(i % 3) * 0.06} className={`glass relative flex h-full flex-col overflow-hidden rounded-3xl p-7 ${p.big ? "ring-1 ring-signal/30" : ""}`}>
                {p.big ? <span aria-hidden="true" className="absolute -right-10 -top-10 size-56 rounded-full bg-[radial-gradient(closest-side,var(--glow),transparent)]" /> : null}
                <span className="text-5xl font-bold tracking-[-0.05em]">
                  <NumberTicker value={p.v} decimals={p.d ?? 0} suffix={p.suffix} />
                  {p.of ? <span className="text-3xl text-muted-foreground"> {p.of}</span> : null}
                </span>
                <span className="mt-3 text-base font-semibold">{p.l}</span>
                <span className="mt-1 text-sm text-muted-foreground">{p.n}</span>
              </ScrollReveal>
          ))}
        </ul>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Measured on generated tickets, not on a customer&apos;s data.{" "}
          <Link href="/dataset" className="font-semibold text-signal underline underline-offset-4">How it was tested</Link>
        </p>
      </section>

      {/* Rooms */}
      <section aria-labelledby="rooms" className="mx-auto max-w-6xl px-5 py-20">
        <SectionHead id="rooms" eyebrow="The product" title="One workspace. Six rooms." />
        <ul className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {ROOMS.map(({ Icon, t, d, href }, i) => (
            <ScrollReveal as="li" key={t} delay={(i % 3) * 0.06} className="h-full">
                <Link href={href} className="glass group flex h-full items-start gap-4 rounded-3xl p-6 transition-transform hover:-translate-y-1">
                  <span aria-hidden="true" className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent text-signal">
                    <Icon className="size-5" />
                  </span>
                  <span>
                    <span className="flex items-center gap-1.5 text-lg font-bold tracking-[-0.02em]">
                      {t} <ArrowRight aria-hidden="true" className="size-4 opacity-0 transition-opacity group-hover:opacity-100" />
                    </span>
                    <span className="mt-1 block text-sm text-muted-foreground">{d}</span>
                  </span>
                </Link>
              </ScrollReveal>
          ))}
        </ul>
      </section>

      {/* Trust */}
      <section aria-labelledby="trust" className="mx-auto max-w-6xl px-5 py-20">
        <SectionHead id="trust" eyebrow="Trust" title="Safe by default." />
        <ul className="mt-14 grid grid-cols-1 gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
          {TRUST.map(({ Icon, t, d }, i) => (
            <ScrollReveal as="li" key={t} delay={(i % 3) * 0.05} className="flex  items-start gap-4">
                <Icon aria-hidden="true" className="mt-0.5 size-6 shrink-0 text-signal" />
                <span>
                  <span className="block font-bold">{t}</span>
                  <span className="mt-1 block text-sm text-muted-foreground">{d}</span>
                </span>
              </ScrollReveal>
          ))}
        </ul>
        <p className="mt-10 text-center">
          <Link href="/architecture" className="inline-flex items-center gap-1.5 font-semibold text-signal underline underline-offset-4">
            See the architecture <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </p>
      </section>

      {/* FAQ */}
      <section aria-labelledby="faq" className="mx-auto max-w-3xl px-5 py-20">
        <SectionHead id="faq" eyebrow="Questions" title="Straight answers." />
        <div className="mt-12 divide-y rounded-3xl border bg-card/60">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group px-6 py-5 [&_summary::-webkit-details-marker]:hidden">
              <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 text-lg font-semibold">
                {q}
                <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full border text-muted-foreground transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="mt-2 pr-10 leading-relaxed text-muted-foreground">{a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section aria-labelledby="cta" className="mx-auto max-w-6xl px-5 py-10">
        <ScrollReveal>
          <div className="relative overflow-hidden rounded-[32px] bg-[#0c0c0e] px-6 py-16 text-center text-[#faf8f5] sm:py-20">
            <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(ellipse_60%_80%_at_50%_120%,rgba(217,45,32,.45),transparent)]" />
            <div className="relative">
              <h2 id="cta" className="text-[clamp(2rem,5vw,3.5rem)] font-bold leading-[1.02] tracking-[-0.045em]">See your next ticket clearly.</h2>
              <p className="mx-auto mt-4 max-w-md text-[#c9c5bf]">Start with an example, or sign in with your workspace key.</p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link href="/intake" className="workspace-button primary !min-h-12 !rounded-2xl !px-6">
                  Open the app <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
                <Link href="/docs" className="inline-flex min-h-12 items-center rounded-2xl border border-white/20 px-6 text-sm font-semibold text-[#faf8f5] hover:bg-white/10">
                  Read the docs
                </Link>
              </div>
            </div>
          </div>
        </ScrollReveal>
      </section>
    </div>
  );
}
