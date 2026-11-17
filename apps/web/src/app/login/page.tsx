"use client";

import { ArrowRight, BookOpen, Database, Eye, EyeOff, KeyRound, Lock, ShieldCheck, TimerReset, Waypoints } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { MonolithMark, Wordmark } from "@/components/brand/monolith";
import { Reveal } from "@/components/motion";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { PipelineTrack } from "@/components/viz/pipeline";

const PROOF = [
  { value: "455 / 455", label: "auto-routed tickets correct", note: "frozen synthetic test" },
  { value: "40 ms", label: "median pipeline time", note: "typical ticket, INT8 on CPU" },
  { value: "0", label: "LLMs deciding where tickets go", note: "calibrated encoder + rules" },
];

const GUARANTEES = [
  { Icon: Lock, label: "Key sealed with AES-GCM" },
  { Icon: TimerReset, label: "1-hour strict session" },
  { Icon: ShieldCheck, label: "Same-origin requests only" },
  { Icon: Waypoints, label: "Row-level tenant isolation" },
];

export default function LoginPage() {
  const [apiKey, setApiKey] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();

  return (
    <div className="relative min-h-dvh">
      <div className="atmosphere" aria-hidden="true" />
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Link href="/" aria-label="ResolveIT home" className="rounded-lg">
          <Wordmark />
        </Link>
        <ThemeToggle />
      </header>
      <main id="main" tabIndex={-1} className="mx-auto grid outline-none max-w-6xl items-center gap-10 px-5 pb-16 pt-4 lg:grid-cols-[1.1fr_1fr] lg:pt-10">
        <Reveal className="order-2 lg:order-1">
          <p className="eyebrow inline-flex items-center gap-2">
            <span aria-hidden="true" className="h-px w-6 bg-signal" /> Incident intelligence for IT teams
          </p>
          <h1 className="text-gradient text-[clamp(2.4rem,5.5vw,4.25rem)] font-bold leading-[0.98] tracking-[-0.05em]">
            Ambiguity in.
            <br />
            One <span className="text-signal [-webkit-text-fill-color:var(--signal)]">calibrated</span> path out.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            People describe IT problems in their own words. ResolveIT shows what it understood, then routes the ticket, asks one question, or hands it
            to a person, and always says why.
          </p>
          <div className="glass mt-8 rounded-2xl p-5">
            <PipelineTrack active={4} />
          </div>
          <ul className="mt-6 grid gap-3 sm:grid-cols-3">
            {PROOF.map((p) => (
              <li key={p.label} className="glass rounded-2xl p-4">
                <span className="block text-2xl font-bold tracking-[-0.04em] tabular">{p.value}</span>
                <span className="mt-1 block text-xs font-medium">{p.label}</span>
                <span className="mt-0.5 block font-mono text-xs uppercase tracking-wider text-muted-foreground">{p.note}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted-foreground">Measured on generated tickets, not on a customer&apos;s data. See the data and model page for the details.</p>
        </Reveal>

        <Reveal className="order-1 lg:order-2" delay={0.06}>
          <section aria-labelledby="signin-title" className="glass-strong relative overflow-hidden rounded-3xl p-6 shadow-2xl sm:p-8">
            <div aria-hidden="true" className="pointer-events-none absolute -right-16 -top-16 size-56 rounded-full bg-[radial-gradient(closest-side,var(--glow),transparent)]" />
            <MonolithMark size={44} animate />
            <p className="eyebrow mt-6">Secure access</p>
            <h2 id="signin-title" className="text-2xl font-bold tracking-[-0.03em]">Your workspace. Your identity.</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Sign in with the individual API credential your administrator issued. Your role and review identity come from it.
            </p>
            <form
              className="mt-6"
              onSubmit={async (event) => {
                event.preventDefault();
                setBusy(true);
                setMessage("");
                try {
                  const response = await fetch("/api/session", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ apiKey }) });
                  const result = await response.json();
                  if (!response.ok) throw new Error(result.detail ?? "Sign-in failed");
                  setApiKey("");
                  router.replace("/intake");
                  router.refresh();
                } catch (error) {
                  setMessage(error instanceof Error ? error.message : "Sign-in failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label className="text-sm font-semibold" htmlFor="api-credential">Individual API credential</label>
              <div className="relative mt-2">
                <KeyRound aria-hidden="true" className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  id="api-credential"
                  className="field-input !min-h-12 !rounded-xl pl-10 pr-12 font-mono"
                  type={show ? "text" : "password"}
                  autoComplete="current-password"
                  spellCheck={false}
                  maxLength={512}
                  required
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  aria-label={show ? "Hide credential" : "Show credential"}
                  aria-pressed={show}
                  className="absolute right-1.5 top-1/2 grid size-10 -translate-y-1/2 place-items-center rounded-lg text-muted-foreground hover:text-foreground"
                >
                  {show ? <EyeOff aria-hidden="true" className="size-4" /> : <Eye aria-hidden="true" className="size-4" />}
                </button>
              </div>
              <button className="workspace-button primary mt-5 !min-h-12 w-full !rounded-xl text-[15px]" disabled={busy || !apiKey}>
                {busy ? "Signing in…" : "Sign in"}
                {busy ? null : <ArrowRight aria-hidden="true" className="size-4" />}
              </button>
            </form>
            <button
              type="button"
              className="mt-3 w-full rounded-xl py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground"
              onClick={async () => {
                const result = await fetch("/api/session", { method: "DELETE" });
                if (result.ok) {
                  setMessage("Signed out. Session cleared.");
                  router.refresh();
                }
              }}
            >
              Clear current session
            </button>
            <p role="status" className={`min-h-5 text-center text-sm ${message.startsWith("Signed out") ? "text-muted-foreground" : "text-risk"}`}>{message}</p>
            <ul className="mt-4 grid grid-cols-2 gap-2 border-t pt-5">
              {GUARANTEES.map(({ Icon, label }) => (
                <li key={label} className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Icon aria-hidden="true" className="size-3.5 shrink-0 text-signal" /> {label}
                </li>
              ))}
            </ul>
            <p className="mt-5 text-xs leading-relaxed text-muted-foreground">
              No key yet? Credentials are issued per person by your workspace admin. Nothing you type here is stored in the browser.
            </p>
          </section>
          <nav aria-label="Learn without signing in" className="mt-4 grid grid-cols-2 gap-3">
            <Link href="/docs" className="glass flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold hover:border-foreground/30">
              <BookOpen aria-hidden="true" className="size-4 text-signal" /> How it works
            </Link>
            <Link href="/dataset" className="glass flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold hover:border-foreground/30">
              <Database aria-hidden="true" className="size-4 text-signal" /> Data &amp; model
            </Link>
          </nav>
        </Reveal>
      </main>
    </div>
  );
}
