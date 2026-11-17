import {
  ArrowRight,
  Bot,
  BookOpen,
  Briefcase,
  Cloud,
  Code2,
  Database,
  Eye,
  FileWarning,
  FlaskConical,
  GitBranch,
  HardDrive,
  Inbox,
  KeyRound,
  Library,
  Lock,
  Mail,
  Network,
  Printer,
  Route,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  Timer,
  Users,
  UsersRound,
  Waypoints,
} from "lucide-react";
import type { Metadata } from "next";

import { PageHero } from "@/components/landing/page-hero";
import Link from "next/link";

import { GlassCard, ScrollReveal } from "@/components/motion";
import { GUIDES } from "@/lib/guides";

export const metadata: Metadata = { title: "Docs" };

const NAV = [
  ["start", "Start here"],
  ["rooms", "Using each page"],
  ["read", "Reading a result"],
  ["concepts", "Key ideas"],
  ["teams", "Teams and details"],
  ["safety", "Safety and privacy"],
  ["glossary", "Glossary"],
  ["more", "Go deeper"],
] as const;

const FIRST = [
  ["Get a key", "Your admin issues a personal key. One per person."],
  ["Sign in", "Paste it on the sign-in page. Sessions last one hour."],
  ["Report a problem", "Type it like you'd say it, or load an example."],
  ["Read the result", "See what was understood, and what happens next."],
];

const ROOMS = [
  { Icon: Inbox, t: "Report a problem", href: "/intake", g: GUIDES.intake, who: "Everyone" },
  { Icon: UsersRound, t: "Review", href: "/review", g: GUIDES.review, who: "Reviewers" },
  { Icon: Waypoints, t: "Bounce analyzer", href: "/bounce", g: GUIDES.bounce, who: "Service-desk leads" },
  { Icon: FlaskConical, t: "Evaluation", href: "/evaluation", g: GUIDES.evaluation, who: "Admins, auditors" },
  { Icon: Bot, t: "Agent hand-off", href: "/mcp", g: GUIDES.mcp, who: "Developers" },
  { Icon: Settings2, t: "Settings", href: "/settings", g: GUIDES.settings, who: "Admins" },
];

const CALLOUTS = [
  ["Decision", "Route, ask, or a person, in one line."],
  ["Confidence", "How likely the top team is. Calibrated, not a promise."],
  ["Plausible teams", "Teams that can't be ruled out. One means sure."],
  ["Trade-off", "Expected delay if routed vs. if a person triages."],
  ["Evidence", "Your own words, underlined, labelled by detail."],
];

const CONCEPTS = [
  { Icon: Route, t: "Three outcomes", d: "Route when sure. Ask one question when it settles things. Hand to a person when unsure, conflicting, or security." },
  { Icon: Eye, t: "Evidence first", d: "Every detail it uses is linked to the exact words in the report. Nothing is invented." },
  { Icon: ShieldCheck, t: "Proven, not hoped", d: "A team gets automatic routing only when the chance of a wrong route is proven to be 5% or less." },
  { Icon: Timer, t: "Shadow mode", d: "New workspaces only suggest. They route on their own after passing a test on their own reviewed tickets." },
];

const SLOTS = ["System or app", "Part affected", "What happens", "Who is affected", "When it started", "How often", "Where you are", "Error code", "Recent change", "Office or site", "Urgency"];

const TEAMS = [
  { Icon: Network, n: "Network" },
  { Icon: KeyRound, n: "Identity & Access" },
  { Icon: Mail, n: "Email & Collaboration" },
  { Icon: HardDrive, n: "Hardware & Endpoint" },
  { Icon: FileWarning, n: "Software & Licensing" },
  { Icon: Database, n: "Database" },
  { Icon: Cloud, n: "Cloud Infrastructure" },
  { Icon: ShieldAlert, n: "Security" },
  { Icon: Briefcase, n: "ERP & Finance" },
  { Icon: Users, n: "HR Systems" },
  { Icon: GitBranch, n: "DevOps & CI/CD" },
  { Icon: Printer, n: "Facilities & AV" },
];

const SAFETY = [
  ["Saved before analysed", "Encrypted and stored before any model runs."],
  ["Personal data masked", "Emails, phones, Aadhaar and PAN hidden from the model."],
  ["No LLM decides", "Rules and a small trained model. Agents can only propose."],
  ["Security escalates", "Security reports skip questions and reach a person now."],
  ["Workspaces isolated", "Database row-level security on every customer table."],
  ["Right to erasure", "Admins can erase every incident tied to a person."],
];

const GLOSSARY = [
  ["Incident frame", "The 11 details read from a report, each marked found, unclear, conflicting or not stated."],
  ["Calibrated", "A confidence that means what it says: of tickets at 80%, about 80% are right."],
  ["Plausible set", "The teams that can't be ruled out. It contains the right team about 90% of the time."],
  ["Risk certificate", "A statistical proof that wrong automatic routes stay at or below 5%."],
  ["Bundle", "The model plus every threshold, checked by fingerprint before it runs."],
  ["Bounce", "A ticket being passed from one queue to another."],
  ["MCP", "Model Context Protocol: a standard way for AI agents to call tools."],
];

function H({ id, n, t, sub }: { id: string; n: string; t: string; sub?: string }) {
  return (
    <ScrollReveal className="mb-6">
      <p className="eyebrow">{n}</p>
      <h2 id={`h-${id}`} className="text-[clamp(1.6rem,3.2vw,2.25rem)] font-bold tracking-[-0.04em]">{t}</h2>
      {sub ? <p className="mt-2 max-w-xl text-muted-foreground">{sub}</p> : null}
    </ScrollReveal>
  );
}

export default function DocsPage() {
  return (
    <>
      <PageHero
        eyebrow="Docs"
        title="Everything, explained simply."
        sub="Start here, then dip in where you need to. Each section takes about a minute."
        stats={[
          { label: "Sections", value: NAV.length },
          { label: "Outcomes", value: "Route · Ask · Hand off" },
          { label: "Teams", value: "12" },
          { label: "Languages", value: "English · हिन्दी · Hinglish" },
        ]}
      />
    <div className="mx-auto max-w-6xl px-5 pt-12">
      <div className="mt-12 grid gap-12 lg:grid-cols-[200px_1fr]">
        <nav aria-label="Docs sections" className="top-24 hidden self-start lg:sticky lg:block">
          <ol className="space-y-1 border-l">
            {NAV.map(([id, label], i) => (
              <li key={id}>
                <a href={`#${id}`} className="-ml-px flex gap-2 border-l border-transparent py-1.5 pl-4 text-sm text-muted-foreground hover:border-signal hover:text-foreground">
                  <span className="font-mono text-xs">{String(i + 1).padStart(2, "0")}</span>
                  {label}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="min-w-0 space-y-24">
          <section id="start" aria-labelledby="h-start" className="scroll-mt-24">
            <H id="start" n="01 · Start here" t="Your first five minutes." />
            <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {FIRST.map(([t, d], i) => (
                <ScrollReveal as="li" key={t} delay={i * 0.06} className="glass relative rounded-2xl p-5">
                  <span className="grid size-8 place-items-center rounded-full bg-foreground font-mono text-xs font-bold text-background">{i + 1}</span>
                  <h3 className="mt-4 font-bold">{t}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{d}</p>
                </ScrollReveal>
              ))}
            </ol>
            <p className="mt-4 text-sm text-muted-foreground">
              No key? Try the <Link href="/#try" className="font-semibold text-signal underline underline-offset-4">live preview</Link> or the{" "}
              <Link href="/examples" className="font-semibold text-signal underline underline-offset-4">30 examples</Link>.
            </p>
          </section>

          <section id="rooms" aria-labelledby="h-rooms" className="scroll-mt-24">
            <H id="rooms" n="02 · Using each page" t="Six pages, three steps each." />
            <ul className="grid gap-4 md:grid-cols-2">
              {ROOMS.map(({ Icon, t, href, g, who }, i) => (
                <ScrollReveal as="li" key={t} delay={(i % 2) * 0.06}>
                  <GlassCard className="h-full p-6">
                    <div className="flex items-center gap-3">
                      <span aria-hidden="true" className="grid size-10 place-items-center rounded-xl bg-accent text-signal">
                        <Icon className="size-5" />
                      </span>
                      <div>
                        <h3 className="font-bold">{t}</h3>
                        <p className="text-xs text-muted-foreground">For {who.toLowerCase()}</p>
                      </div>
                    </div>
                    <ol className="mt-5 space-y-2.5">
                      {g.map((s, k) => (
                        <li key={s} className="flex gap-3 text-sm">
                          <span className="font-mono text-xs text-signal">{k + 1}</span>
                          <span>{s}</span>
                        </li>
                      ))}
                    </ol>
                    <Link href={href} className="mt-5 inline-flex min-h-10 items-center gap-1.5 text-sm font-semibold text-signal">
                      Open {t} <ArrowRight aria-hidden="true" className="size-4" />
                    </Link>
                  </GlassCard>
                </ScrollReveal>
              ))}
            </ul>
          </section>

          <section id="read" aria-labelledby="h-read" className="scroll-mt-24">
            <H id="read" n="03 · Reading a result" t="Five things on every result." sub="An illustration of a routed ticket, with each part labelled." />
            <div className="grid items-start gap-6 lg:grid-cols-[1.1fr_1fr]">
              <ScrollReveal>
                <figure className="glass rounded-3xl p-6" aria-label="Illustration of a result card">
                  <div className="flex items-start gap-4">
                    <span className="relative grid size-12 place-items-center rounded-2xl bg-primary text-primary-foreground" aria-hidden="true">
                      <Route className="size-6" />
                    </span>
                    <div>
                      <p className="mono-label">Decision · route <span className="ml-1 rounded-full bg-foreground px-1.5 text-[10px] text-background">1</span></p>
                      <p className="text-2xl font-bold tracking-[-0.03em]">Sent to Network</p>
                    </div>
                  </div>
                  <div className="mt-5 grid grid-cols-2 gap-3">
                    <div className="rounded-2xl border bg-card p-4">
                      <p className="mono-label">Confidence <span className="ml-1 rounded-full bg-foreground px-1.5 text-[10px] text-background">2</span></p>
                      <p className="mt-1 text-3xl font-bold">86%</p>
                    </div>
                    <div className="rounded-2xl border bg-card p-4">
                      <p className="mono-label">Plausible <span className="ml-1 rounded-full bg-foreground px-1.5 text-[10px] text-background">3</span></p>
                      <p className="mt-2 inline-block rounded-full border border-signal/40 bg-accent px-2.5 py-1 text-xs font-semibold text-accent-foreground">Network</p>
                    </div>
                  </div>
                  <div className="mt-3 rounded-2xl border bg-card p-4">
                    <p className="mono-label">Trade-off <span className="ml-1 rounded-full bg-foreground px-1.5 text-[10px] text-background">4</span></p>
                    <div className="mt-2 space-y-2 text-xs">
                      <div className="flex items-center gap-3"><span className="w-28">If routed</span><span className="h-2 w-[20%] rounded-full bg-primary" /><span className="font-mono">10 min</span></div>
                      <div className="flex items-center gap-3"><span className="w-28">If a person triages</span><span className="h-2 w-[80%] rounded-full bg-foreground/60" /><span className="font-mono">45 min</span></div>
                    </div>
                  </div>
                  <p className="mt-3 rounded-2xl border bg-card p-4 text-lg">
                    <span className="mono-label mr-2">Evidence <span className="rounded-full bg-foreground px-1.5 text-[10px] text-background">5</span></span>
                    <span className="underline decoration-signal decoration-2 underline-offset-4">VPN</span> keeps dropping for the{" "}
                    <span className="underline decoration-signal decoration-2 underline-offset-4">whole floor</span>
                  </p>
                  <figcaption className="mt-3 text-xs text-muted-foreground">Illustration. Real results appear on the Report a problem page.</figcaption>
                </figure>
              </ScrollReveal>
              <ol className="space-y-3">
                {CALLOUTS.map(([t, d], i) => (
                  <ScrollReveal as="li" key={t} delay={i * 0.05} className="flex items-start gap-4 rounded-2xl border bg-card/60 p-4">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-foreground font-mono text-xs font-bold text-background">{i + 1}</span>
                    <span>
                      <span className="block font-bold">{t}</span>
                      <span className="block text-sm text-muted-foreground">{d}</span>
                    </span>
                  </ScrollReveal>
                ))}
              </ol>
            </div>
          </section>

          <section id="concepts" aria-labelledby="h-concepts" className="scroll-mt-24">
            <H id="concepts" n="04 · Key ideas" t="Four ideas behind every decision." />
            <ul className="grid gap-4 sm:grid-cols-2">
              {CONCEPTS.map(({ Icon, t, d }, i) => (
                <ScrollReveal as="li" key={t} delay={(i % 2) * 0.06}>
                  <GlassCard tilt className="h-full p-6">
                    <Icon aria-hidden="true" className="size-6 text-signal" />
                    <h3 className="mt-4 text-lg font-bold">{t}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{d}</p>
                  </GlassCard>
                </ScrollReveal>
              ))}
            </ul>
          </section>

          <section id="teams" aria-labelledby="h-teams" className="scroll-mt-24">
            <H id="teams" n="05 · Teams and details" t="Twelve teams. Eleven details." sub="Every report is read for the same 11 details, then matched to one of 12 teams you map to your own queues." />
            <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {SLOTS.map((s, i) => (
                <li key={s} className="flex items-center gap-2 rounded-xl border bg-card/60 px-3 py-2.5 text-sm">
                  <span className="font-mono text-[10px] text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
                  {s}
                </li>
              ))}
            </ul>
            <ul className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {TEAMS.map(({ Icon, n }) => (
                <li key={n} className="glass flex flex-col gap-3 rounded-2xl p-4">
                  <Icon aria-hidden="true" className="size-5 text-signal" />
                  <span className="text-sm font-semibold leading-tight">{n}</span>
                </li>
              ))}
            </ul>
          </section>

          <section id="safety" aria-labelledby="h-safety" className="scroll-mt-24">
            <H id="safety" n="06 · Safety and privacy" t="What it will never do." />
            <ul className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
              {SAFETY.map(([t, d]) => (
                <li key={t} className="flex gap-3">
                  <Lock aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-signal" />
                  <span>
                    <span className="block font-bold">{t}</span>
                    <span className="block text-sm text-muted-foreground">{d}</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section id="glossary" aria-labelledby="h-glossary" className="scroll-mt-24">
            <H id="glossary" n="07 · Glossary" t="Words you'll see." />
            <dl className="divide-y rounded-3xl border bg-card/60">
              {GLOSSARY.map(([t, d]) => (
                <div key={t} className="grid gap-1 px-6 py-4 sm:grid-cols-[180px_1fr]">
                  <dt className="font-bold">{t}</dt>
                  <dd className="text-sm text-muted-foreground">{d}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section id="more" aria-labelledby="h-more" className="scroll-mt-24">
            <H id="more" n="08 · Go deeper" t="For builders and evaluators." />
            <ul className="grid gap-4 sm:grid-cols-2">
              {[
                { Icon: Code2, t: "API reference", d: "Every endpoint, field and status code.", href: "/docs/api" },
                { Icon: BookOpen, t: "Architecture", d: "Animated system map and request lifecycle.", href: "/architecture" },
                { Icon: Library, t: "Examples", d: "30 real tickets with recorded outcomes.", href: "/examples" },
                { Icon: Database, t: "Data & model", d: "How it was trained and tested.", href: "/dataset" },
              ].map(({ Icon, t, d, href }) => (
                <li key={t}>
                  <Link href={href} className="glass group flex items-center gap-4 rounded-2xl p-5 transition-transform hover:-translate-y-0.5">
                    <Icon aria-hidden="true" className="size-6 shrink-0 text-signal" />
                    <span className="flex-1">
                      <span className="block font-bold">{t}</span>
                      <span className="block text-sm text-muted-foreground">{d}</span>
                    </span>
                    <ArrowRight aria-hidden="true" className="size-4 text-muted-foreground transition-transform group-hover:translate-x-1" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
    </>
  );
}
