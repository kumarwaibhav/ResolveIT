"use client";

import { ArrowRight, Menu, X } from "lucide-react";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { MonolithMark, Wordmark } from "@/components/brand/monolith";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { useModal } from "@/lib/use-modal";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/#how", label: "How it works" },
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
        <div
          className={cn(
            "mx-auto flex h-14 max-w-6xl items-center gap-3 rounded-2xl px-3 transition-all duration-300 sm:px-4",
            scrolled ? "glass" : "border border-transparent",
          )}
        >
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

      <footer inert={open} className="mx-auto mt-24 max-w-6xl border-t px-5 pb-12 pt-12">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Wordmark />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted-foreground">Incident intelligence that shows its work. Routes when sure, asks when not, escalates when it matters.</p>
          </div>
          {[
            { h: "Product", l: [["Report a problem", "/intake"], ["Review", "/review"], ["Bounce analyzer", "/bounce"], ["Evaluation", "/evaluation"]] },
            { h: "Learn", l: [["Docs", "/docs"], ["Examples", "/examples"], ["Architecture", "/architecture"], ["Data & model", "/dataset"]] },
            { h: "Developers", l: [["API reference", "/docs/api"], ["Agent hand-off (MCP)", "/mcp"], ["Sign in", "/login"]] },
          ].map((col) => (
            <div key={col.h}>
              <h2 className="mono-label">{col.h}</h2>
              <ul className="mt-2">
                {col.l.map(([label, href]) => (
                  <li key={href}>
                    <Link href={href!} className="inline-flex min-h-11 items-center text-sm text-muted-foreground transition-colors hover:text-foreground">
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 flex flex-wrap items-center justify-between gap-3 border-t pt-6 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-2">
            <MonolithMark size={16} /> © 2026 ResolveIT
          </span>
          <span>
            English · <span lang="hi">हिन्दी</span> · Hinglish
          </span>
        </div>
      </footer>
    </div>
  );
}
