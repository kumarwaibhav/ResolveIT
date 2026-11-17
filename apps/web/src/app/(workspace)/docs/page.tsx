import {
  AppWindow,
  Briefcase,
  Cloud,
  Cpu,
  Database,
  DoorOpen,
  EyeOff,
  FileWarning,
  GitBranch,
  HardDrive,
  KeyRound,
  Lock,
  Mail,
  MessageCircleQuestion,
  Network,
  Printer,
  Route,
  Server,
  ShieldAlert,
  ShieldCheck,
  Timer,
  UserRound,
  Users,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ArchitectureExplorer } from "@/components/architecture-explorer";
import { GlassCard, Reveal } from "@/components/motion";
import { WorkspaceHeading } from "@/components/workspace-heading";

export const metadata: Metadata = { title: "How it works" };

const TOC = [
  ["outcomes", "Three outcomes"],
  ["path", "The decision path"],
  ["frame", "The incident frame"],
  ["teams", "Twelve teams"],
  ["architecture", "Architecture"],
  ["safety", "Safety"],
  ["api", "API"],
  ["glossary", "Glossary"],
] as const;

const OUTCOMES = [
  {
    Icon: Route,
    name: "Route",
    when: "The model is confident and the risk certificate for that team holds.",
    example: "“Outlook keeps crashing for the whole floor since this morning” → Email & Collaboration",
    hl: true,
  },
  {
    Icon: MessageCircleQuestion,
    name: "Ask",
    when: "One answer would clearly improve the routing, and asking is worth the wait.",
    example: "“kal se kuch bhi kaam nahi kar raha” → “Which system or app is this about?”",
  },
  {
    Icon: UserRound,
    name: "Defer",
    when: "Too many teams fit, details conflict, the tenant is in shadow mode, or it looks like a security incident.",
    example: "“I clicked a link and typed my password…” → a person, flagged for Security",
  },
];

const SLOTS = [
  ["System or app", "Outlook, VPN, SAP"],
  ["Part affected", "login, sync, display"],
  ["What happens", "crashes, cannot connect"],
  ["Who is affected", "me, my team, the floor"],
  ["When it started", "since this morning"],
  ["How often", "every few minutes"],
  ["Where you are", "office, home, VPN"],
  ["Error code", "0x80070005"],
  ["Recent change", "after the update"],
  ["Office or site", "Pune, 4th floor"],
  ["Urgency", "urgent, blocking"],
] as const;

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
  { Icon: Lock, t: "Saved before analysed", d: "Every report is encrypted and stored before any model runs." },
  { Icon: EyeOff, t: "Identifiers masked", d: "Emails, phones, Aadhaar and PAN are masked before the model reads the text." },
  { Icon: ShieldCheck, t: "No LLM decides", d: "Routing uses rules plus a calibrated encoder. Agents can propose, never decide." },
  { Icon: ShieldAlert, t: "Security escalates", d: "A security signal skips questions and goes straight to a person." },
  { Icon: Users, t: "Tenants isolated", d: "Postgres row-level security on every tenant table, enforced for the app role." },
  { Icon: KeyRound, t: "Keys stay server-side", d: "The browser never holds an API key; sessions are sealed with AES-GCM for one hour." },
  { Icon: Timer, t: "Shadow mode first", d: "Real tenants get suggestions only until certified on their own reviewed tickets." },
  { Icon: DoorOpen, t: "Right to erasure", d: "Admins can erase every incident linked to a person's identifier." },
];

const API = [
  ["POST", "/v1/incidents", "admin · reviewer · agent", "Report a problem; returns the frame and decision"],
  ["GET", "/v1/incidents/{id}", "any role", "Read one incident (agents never see decrypted text)"],
  ["POST", "/v1/incidents/{id}/answer", "admin · reviewer", "Answer or skip the optional question"],
  ["POST", "/mcp", "agent · admin", "Model Context Protocol endpoint for AI agents"],
  ["GET", "/v1/review", "admin · reviewer", "Blind review queue"],
  ["POST", "/v1/review/{id}/labels", "admin · reviewer", "Save an independent human label"],
  ["GET · PUT", "/v1/settings", "admin", "Queue map, costs and timezone"],
  ["POST", "/v1/privacy/erasure", "admin", "Erase a subject's incidents"],
  ["POST", "/v1/bounce/analyze", "admin · reviewer", "Analyse an assignment-history CSV"],
  ["GET", "/v1/evaluation", "admin · reviewer · viewer", "Bundle provenance and certification status"],
] as const;

const GLOSSARY = [
  ["Incident frame", "The 11 details read from a report, each marked found, unclear, conflicting or not stated, with the exact words as evidence."],
  ["Calibrated probability", "A confidence that means what it says: of tickets given 80%, about 80% belong to that team."],
  ["Plausible-team set", "The teams that cannot be ruled out. It contains the right team about 90% of the time; one team means confident."],
  ["Risk certificate", "A statistical proof that, for a team, wrong auto-routes stay at or below 5% with 95% confidence."],
  ["Shadow mode", "The system suggests a team but a person decides. Default for every real tenant."],
  ["Bundle", "The model plus every threshold and cost, verified by hash at load. Change anything and it is a new bundle."],
  ["Bounce", "A ticket being reassigned from one queue to another."],
] as const;

function ArchitectureDiagram() {
  const box = "fill-[var(--card)] stroke-[var(--border)]";
  return (
    <svg viewBox="0 0 760 300" className="h-auto w-full" role="img" aria-label="Architecture: browsers and AI agents reach the web app and the API; the API uses a Postgres database with row-level security and a verified INT8 model bundle.">
      <defs>
        <marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0L10 5L0 10z" fill="var(--muted-foreground)" />
        </marker>
      </defs>
      <g fontFamily="inherit" fill="var(--foreground)">
        <rect x="10" y="40" width="150" height="70" rx="14" className={box} />
        <text x="85" y="72" textAnchor="middle" fontSize="14" fontWeight="700">People</text>
        <text x="85" y="92" textAnchor="middle" fontSize="11" fill="var(--muted-foreground)">browser</text>
        <rect x="10" y="190" width="150" height="70" rx="14" className={box} />
        <text x="85" y="222" textAnchor="middle" fontSize="14" fontWeight="700">AI agents</text>
        <text x="85" y="242" textAnchor="middle" fontSize="11" fill="var(--muted-foreground)">MCP clients</text>

        <rect x="230" y="40" width="170" height="70" rx="14" fill="var(--card)" stroke="var(--signal)" strokeWidth="1.5" />
        <text x="315" y="70" textAnchor="middle" fontSize="14" fontWeight="700">Web app</text>
        <text x="315" y="90" textAnchor="middle" fontSize="11" fill="var(--muted-foreground)">Next.js · Vercel Mumbai</text>

        <rect x="470" y="110" width="150" height="80" rx="14" fill="var(--card)" stroke="var(--signal)" strokeWidth="1.5" />
        <text x="545" y="145" textAnchor="middle" fontSize="14" fontWeight="700">Decision API</text>
        <text x="545" y="165" textAnchor="middle" fontSize="11" fill="var(--muted-foreground)">FastAPI · Modal</text>

        <rect x="650" y="30" width="100" height="80" rx="14" className={box} />
        <text x="700" y="64" textAnchor="middle" fontSize="13" fontWeight="700">Postgres</text>
        <text x="700" y="82" textAnchor="middle" fontSize="10" fill="var(--muted-foreground)">RLS · Neon</text>
        <rect x="650" y="190" width="100" height="80" rx="14" className={box} />
        <text x="700" y="224" textAnchor="middle" fontSize="13" fontWeight="700">Model</text>
        <text x="700" y="242" textAnchor="middle" fontSize="10" fill="var(--muted-foreground)">INT8 bundle</text>
      </g>
      <g fill="none" stroke="var(--muted-foreground)" strokeWidth="1.5" markerEnd="url(#arw)">
        <path d="M160 75H226" />
        <path d="M400 75C440 75 440 150 466 150" />
        <path d="M160 225C320 225 400 170 466 165" />
        <path d="M620 135C640 135 640 70 646 70" />
        <path d="M620 165C640 165 640 230 646 230" />
      </g>
      <g fill="none" stroke="var(--signal)" strokeWidth="2" className="flow-dash">
        <path d="M400 75C440 75 440 150 466 150" />
        <path d="M620 165C640 165 640 230 646 230" />
      </g>
      <text x="430" y="120" fontSize="10" fill="var(--muted-foreground)" textAnchor="middle">key added server-side</text>
    </svg>
  );
}

export default function DocsPage() {
  return (
    <div>
      <WorkspaceHeading
        eyebrow="Learn · How it works"
        title="How ResolveIT decides."
        description="A plain-language tour: what happens to a ticket, the three things that can happen next, and the guarantees that hold every time."
      />

      <nav aria-label="On this page" className="mb-8 flex gap-2 overflow-x-auto pb-1">
        {TOC.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="glass shrink-0 rounded-full px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground">
            {label}
          </a>
        ))}
      </nav>

      <div className="space-y-14">
        <section id="outcomes" aria-labelledby="h-outcomes" className="scroll-mt-24">
          <p className="eyebrow">Three outcomes</p>
          <h2 id="h-outcomes" className="mb-5 text-2xl font-bold tracking-[-0.03em] sm:text-3xl">Every ticket ends in exactly one of these</h2>
          <ul className="grid gap-4 lg:grid-cols-3">
            {OUTCOMES.map(({ Icon, name, when, example, hl }, i) => (
              <Reveal key={name} as="li" delay={i * 0.04}>
                <GlassCard tilt className="h-full p-6">
                  <span aria-hidden="true" className={`grid size-12 place-items-center rounded-2xl ${hl ? "bg-primary text-primary-foreground" : "bg-accent text-signal"}`}>
                    <Icon className="size-6" />
                  </span>
                  <h3 className="mt-5 text-xl font-bold tracking-[-0.02em]">{name}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{when}</p>
                  <p className="mt-4 rounded-xl border bg-card px-3 py-2.5 text-xs leading-relaxed">{example}</p>
                </GlassCard>
              </Reveal>
            ))}
          </ul>
        </section>

        <section id="path" className="scroll-mt-24">
          <ArchitectureExplorer />
        </section>

        <section id="frame" aria-labelledby="h-frame" className="scroll-mt-24">
          <p className="eyebrow">The incident frame</p>
          <h2 id="h-frame" className="text-2xl font-bold tracking-[-0.03em] sm:text-3xl">Eleven details, each with evidence</h2>
          <p className="mb-5 mt-2 max-w-2xl text-sm text-muted-foreground">Missing details never block a ticket. They only shape whether one question is worth asking.</p>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {SLOTS.map(([name, ex], i) => (
              <li key={name} className="glass rounded-2xl p-4">
                <span className="font-mono text-[10px] text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
                <span className="mt-1 block text-sm font-semibold">{name}</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">e.g. {ex}</span>
              </li>
            ))}
          </ul>
        </section>

        <section id="teams" aria-labelledby="h-teams" className="scroll-mt-24">
          <p className="eyebrow">Destinations</p>
          <h2 id="h-teams" className="mb-5 text-2xl font-bold tracking-[-0.03em] sm:text-3xl">Twelve teams, mapped to your queues</h2>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {TEAMS.map(({ Icon, n }) => (
              <li key={n} className="glass flex flex-col items-start gap-3 rounded-2xl p-4">
                <Icon aria-hidden="true" className="size-5 text-signal" />
                <span className="text-sm font-semibold leading-tight">{n}</span>
              </li>
            ))}
          </ul>
        </section>

        <section id="architecture" aria-labelledby="h-arch" className="surface-panel scroll-mt-24">
          <p className="eyebrow">Architecture</p>
          <h2 id="h-arch" className="panel-title">Four moving parts</h2>
          <p className="panel-copy mb-6">The browser only ever talks to the web app, which adds credentials on the server. The API owns every decision; the database isolates tenants; the model bundle is verified by hash before it serves.</p>
          <ArchitectureDiagram />
          <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { Icon: AppWindow, t: "Web app", d: "Next.js 15, React 19. Same-origin only, strict headers." },
              { Icon: Server, t: "Decision API", d: "Python, FastAPI. Rules, model, calibration, risk gate." },
              { Icon: Database, t: "Database", d: "Postgres 16 with row-level security on 20 tables." },
              { Icon: Cpu, t: "Model bundle", d: "INT8 ONNX on CPU, pinned by SHA-256." },
            ].map(({ Icon, t, d }) => (
              <li key={t} className="flex items-start gap-3 rounded-2xl border bg-card/60 p-4">
                <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-signal" />
                <span>
                  <span className="block text-sm font-semibold">{t}</span>
                  <span className="block text-xs text-muted-foreground">{d}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section id="safety" aria-labelledby="h-safety" className="scroll-mt-24">
          <p className="eyebrow">Safety</p>
          <h2 id="h-safety" className="mb-5 text-2xl font-bold tracking-[-0.03em] sm:text-3xl">Guarantees that hold every time</h2>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {SAFETY.map(({ Icon, t, d }, i) => (
              <Reveal key={t} as="li" delay={i * 0.015}>
                <GlassCard className="h-full p-5">
                  <Icon aria-hidden="true" className="size-5 text-signal" />
                  <h3 className="mt-3 text-sm font-bold">{t}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{d}</p>
                </GlassCard>
              </Reveal>
            ))}
          </ul>
        </section>

        <section id="api" aria-labelledby="h-api" className="surface-panel scroll-mt-24">
          <p className="eyebrow">API</p>
          <h2 id="h-api" className="panel-title">The endpoints behind this app</h2>
          <p className="panel-copy">Every call carries a per-person bearer key. Roles decide what each key can do.</p>
          <div tabIndex={0} className="data-table-wrap mt-4">
            <table className="data-table">
              <caption className="sr-only">ResolveIT API endpoints</caption>
              <thead>
                <tr>
                  <th scope="col">Method</th>
                  <th scope="col">Path</th>
                  <th scope="col">Who</th>
                  <th scope="col">Purpose</th>
                </tr>
              </thead>
              <tbody>
                {API.map(([m, p, who, what]) => (
                  <tr key={`${m}${p}`}>
                    <td><span className="rounded-md bg-muted px-2 py-0.5 font-mono text-[11px] font-semibold">{m}</span></td>
                    <td className="whitespace-nowrap font-mono text-xs">{p}</td>
                    <td className="whitespace-nowrap text-xs text-muted-foreground">{who}</td>
                    <td>{what}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section id="glossary" aria-labelledby="h-glossary" className="scroll-mt-24">
          <p className="eyebrow">Glossary</p>
          <h2 id="h-glossary" className="mb-5 text-2xl font-bold tracking-[-0.03em] sm:text-3xl">Words used in this app</h2>
          <dl className="grid gap-3 md:grid-cols-2">
            {GLOSSARY.map(([term, def]) => (
              <div key={term} className="glass rounded-2xl p-5">
                <dt className="text-sm font-bold">{term}</dt>
                <dd className="mt-1 text-sm leading-relaxed text-muted-foreground">{def}</dd>
              </div>
            ))}
          </dl>
        </section>

        <p className="text-sm text-muted-foreground">
          Want the numbers? See <Link href="/dataset" className="font-semibold text-signal underline underline-offset-4">Data &amp; model</Link>.
        </p>
      </div>
    </div>
  );
}
