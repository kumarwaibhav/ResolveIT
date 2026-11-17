"use client";

import { ArrowRight, Menu, X } from "lucide-react";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { MonolithMark, Wordmark } from "@/components/brand/monolith";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { useModal } from "@/lib/use-modal";

const LINKS = [
  { href: "/#demo", label: "How it works" },
  { href: "/examples", label: "Examples" },
  { href: "/architecture", label: "Architecture" },
  { href: "/docs", label: "Docs" },
  { href: "/docs/api", label: "API" },
  { href: "/dataset", label: "Data & model" },
];

export function MarketingShell({ children }: { children: ReactNode }) {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const { scrollY } = useScroll();
  useMotionValueEvent(scrollY, "change", (y) => setScrolled(y > 12));
  useEffect(() => setOpen(false), [pathname]);
  const dialogRef = useModal(open, () => setOpen(false));

  return (
    <div className="relative min-h-dvh">
      <div className="atmosphere" aria-hidden="true" />
      <header inert={open} className="sticky top-0 z-40 px-3 pt-3">
        <div data-scrolled={scrolled} className="nav-pill mx-auto flex h-14 max-w-6xl items-center gap-3 rounded-[20px] pl-4 pr-2 sm:pr-2.5">
          <Link href="/" aria-label="ResolveIT home" className="rounded-lg">
            <Wordmark />
          </Link>
          <nav aria-label="Primary" className="ml-4 hidden flex-1 items-center gap-1 xl:flex">
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                aria-current={pathname === l.href ? "page" : undefined}
                className="whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground aria-[current=page]:text-foreground"
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle className="hidden sm:inline-flex" />
            <Link href="/login" className="hidden min-h-10 items-center whitespace-nowrap rounded-xl px-3 text-sm font-semibold sm:inline-flex">
              Sign in
            </Link>
            <Link href="/intake" className="workspace-button primary !hidden !min-h-10 whitespace-nowrap !rounded-xl !px-4 sm:!inline-flex">
              Open the app <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
            <button
              type="button"
              aria-label="Open menu"
              aria-expanded={open}
              aria-controls="site-menu"
              onClick={() => setOpen(true)}
              className="grid size-11 place-items-center rounded-xl xl:hidden"
            >
              <Menu aria-hidden="true" className="size-5" />
            </button>
          </div>
        </div>
      </header>

      <AnimatePresence>
        {open ? (
          <motion.div
            id="site-menu"
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-label="Site menu"
            className="glass-strong fixed inset-2 z-50 flex flex-col rounded-3xl p-5 xl:hidden"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.18 }}
          >
            <div className="flex items-center justify-between">
              <Wordmark />
              <button type="button" aria-label="Close menu" onClick={() => setOpen(false)} className="grid size-11 place-items-center rounded-xl border bg-card">
                <X aria-hidden="true" className="size-4" />
              </button>
            </div>
            <nav aria-label="Site" className="mt-8 flex flex-col">
              {LINKS.concat({ href: "/login", label: "Sign in" }, { href: "/intake", label: "Open the app" }).map((l) => (
                <Link key={l.href} href={l.href} onClick={() => setOpen(false)} className="border-b py-4 text-2xl font-bold tracking-[-0.03em]">
                  {l.label}
                </Link>
              ))}
            </nav>
            <ThemeToggle className="mt-auto self-start" />
          </motion.div>
        ) : null}
      </AnimatePresence>

      <main id="main" tabIndex={-1} inert={open} className="outline-none">
        {children}
      </main>

      <footer inert={open} className="px-2 pb-2 pt-24 sm:px-3 sm:pb-3">
        {/* Brand block: fixed Signal Crimson in both themes, white text (4.6:1). */}
        <div className="relative overflow-hidden rounded-[28px] bg-[#d92d20] px-6 pt-14 text-white sm:rounded-[40px] sm:px-10 lg:px-14 lg:pt-20">
          <div className="grid gap-12 lg:grid-cols-[1.2fr_2fr]">
            <div>
              <h2 className="text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.02] tracking-[-0.045em]">See your next ticket clearly.</h2>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/intake" className="inline-flex min-h-11 items-center gap-2 rounded-full bg-white px-5 text-sm font-semibold text-[#0c0c0e] transition-transform hover:-translate-y-0.5">
                  Open the app <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
                <Link href="/docs" className="inline-flex min-h-11 items-center rounded-full border border-white/50 px-5 text-sm font-semibold text-white transition-colors hover:bg-white/10">
                  Read the docs
                </Link>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
              {[
                { h: "Product", l: [["Report a problem", "/intake"], ["Review", "/review"], ["Bounce analyzer", "/bounce"], ["Evaluation", "/evaluation"]] },
                { h: "Learn", l: [["Docs", "/docs"], ["Examples", "/examples"], ["Architecture", "/architecture"], ["Data & model", "/dataset"]] },
                { h: "Developers", l: [["API reference", "/docs/api"], ["Agent hand-off (MCP)", "/mcp"], ["Sign in", "/login"]] },
              ].map((col) => (
                <div key={col.h}>
                  <h2 className="text-sm font-semibold">{col.h}</h2>
                  <ul className="mt-2">
                    {col.l.map(([label, href]) => (
                      <li key={href}>
                        <Link href={href!} className="inline-flex min-h-10 items-center text-sm text-white underline-offset-4 hover:underline">
                          {label}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
          <p aria-hidden="true" className="mt-14 flex select-none items-center gap-[0.18em] text-[clamp(3rem,13vw,12rem)] font-bold leading-[0.8] tracking-[-0.06em] [--signal:#d92d20]">
            <MonolithMark size={220} className="h-[0.78em] w-[0.78em] text-white" />
            <span>
              Resolve<span className="font-extrabold">IT</span>
            </span>
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-white/25 py-6 text-xs">
            <span>© 2026 ResolveIT</span>
            <span>
              English · <span lang="hi">हिन्दी</span> · Hinglish
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
