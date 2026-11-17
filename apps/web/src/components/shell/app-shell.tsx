"use client";

import {
  BookOpen,
  Boxes,
  Code2,
  Library,
  Bot,
  Database,
  FlaskConical,
  Inbox,
  LogIn,
  LogOut,
  Menu,
  Route,
  Settings2,
  UsersRound,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useReducedMotion } from "@/lib/use-reduced-motion";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { MonolithMark, Wordmark } from "@/components/brand/monolith";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { useModal } from "@/lib/use-modal";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  hint: string;
  Icon: typeof Inbox;
  admin?: boolean;
}

const WORKSPACE: NavItem[] = [
  { href: "/intake", label: "Report a problem", hint: "Intake", Icon: Inbox },
  { href: "/review", label: "Review", hint: "Human labels", Icon: UsersRound },
  { href: "/bounce", label: "Bounce analyzer", hint: "Handoffs", Icon: Route },
  { href: "/evaluation", label: "Evaluation", hint: "Evidence", Icon: FlaskConical },
  { href: "/mcp", label: "Agent hand-off", hint: "MCP", Icon: Bot },
  { href: "/settings", label: "Settings", hint: "Admin", Icon: Settings2, admin: true },
];
const LEARN: NavItem[] = [
  { href: "/docs", label: "Docs", hint: "Guide", Icon: BookOpen },
  { href: "/examples", label: "Examples", hint: "30 tickets", Icon: Library },
  { href: "/architecture", label: "Architecture", hint: "Diagrams", Icon: Boxes },
  { href: "/docs/api", label: "API reference", hint: "Dev", Icon: Code2 },
  { href: "/dataset", label: "Data & model", hint: "Dataset", Icon: Database },
];

interface Identity {
  tenant_id: string;
  role: string;
  is_synthetic: boolean;
}

function matches(pathname: string, href: string): boolean {
  if (href === "/intake") return pathname === "/intake" || pathname.startsWith("/incidents");
  return pathname === href || pathname.startsWith(`${href}/`);
}
const ALL_HREFS = () => [...WORKSPACE, ...LEARN].map((i) => i.href);
/** The most specific matching link wins, so /docs/api never also lights up /docs. */
function isActive(pathname: string, href: string): boolean {
  const best = ALL_HREFS()
    .filter((h) => matches(pathname, h))
    .sort((a, b) => b.length - a.length)[0];
  return best === href;
}

function NavList({ items, label, pathname, role, onNavigate }: { items: NavItem[]; label: string; pathname: string; role: string | null; onNavigate?: () => void }) {
  const reduce = useReducedMotion();
  return (
    <div>
      <p className="mono-label mb-2 px-3">{label}</p>
      <ul className="space-y-0.5">
        {items.map((item) => {
          const active = isActive(pathname, item.href);
          const locked = item.admin && role !== null && role !== "admin";
          return (
            <li key={item.href} className="relative">
              {active ? (
                <motion.span
                  layoutId={onNavigate ? "nav-pill-m" : "nav-pill"}
                  className="absolute inset-0 rounded-xl border bg-card shadow-sm"
                  transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 34 }}
                />
              ) : null}
              <Link
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors",
                  active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <item.Icon aria-hidden="true" className={cn("size-[18px]", active && "text-signal")} />
                <span className="flex-1">{item.label}</span>
                <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                  {locked ? "admin" : item.hint}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function EngineStatus() {
  const [state, setState] = useState<{ ok: boolean; ms: number; configured?: boolean } | null | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    const started = performance.now();
    fetch("/api/health", { cache: "no-store" })
      .then(async (r) => (r.status === 401 ? null : { ok: r.ok && (await r.json()).ok === true, ms: performance.now() - started, configured: r.status !== 503 }))
      .catch(() => ({ ok: false, ms: performance.now() - started, configured: true }))
      .then((s) => alive && setState(s));
    return () => {
      alive = false;
    };
  }, []);
  if (state === null) return null;
  const label = state === undefined ? "Checking engine" : state.ok ? `Engine ready · ${Math.round(state.ms)} ms` : state.configured === false ? "Engine not connected" : "Engine asleep · wakes on first ticket";
  return (
    <span className="hidden items-center gap-2 whitespace-nowrap rounded-full border bg-card/60 px-3 py-1.5 font-mono text-[11px] text-muted-foreground lg:inline-flex" role="status">
      <span aria-hidden="true" className={cn("size-1.5 rounded-full", state === undefined ? "bg-muted-foreground" : state.ok ? "dot-live" : "bg-warn")} />
      {label}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [identity, setIdentity] = useState<Identity | null | undefined>(undefined);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    fetch("/api/me", { cache: "no-store" })
      .then(async (r) => (r.ok ? ((await r.json()) as Identity) : null))
      .then(setIdentity)
      .catch(() => setIdentity(null));
  }, []);
  useEffect(() => setOpen(false), [pathname]);
  const drawerRef = useModal(open, () => setOpen(false));
  const role = identity ? identity.role : null;
  const current = [...WORKSPACE, ...LEARN].find((i) => isActive(pathname, i.href));

  const signOut = async () => {
    await fetch("/api/session", { method: "DELETE" });
    router.push("/login");
    router.refresh();
  };

  const sidebar = (mobile: boolean) => (
    <>
      <div className="flex items-center justify-between px-3">
        <Link href="/" aria-label="ResolveIT home" className="rounded-lg">
          <Wordmark />
        </Link>
        {mobile ? (
          <button type="button" onClick={() => setOpen(false)} aria-label="Close menu" className="grid size-11 place-items-center rounded-xl border bg-card">
            <X aria-hidden="true" className="size-4" />
          </button>
        ) : null}
      </div>
      <nav aria-label={mobile ? "Main (mobile)" : "Main"} className="mt-8 flex flex-1 flex-col gap-7">
        <NavList items={WORKSPACE} label="Workspace" pathname={pathname} role={role} onNavigate={mobile ? () => setOpen(false) : undefined} />
        <NavList items={LEARN} label="Learn" pathname={pathname} role={role} onNavigate={mobile ? () => setOpen(false) : undefined} />
      </nav>
      <div className="mt-6 rounded-2xl border bg-card/70 p-4">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <span aria-hidden="true" className="size-2 rounded-full bg-ok" />
          Human oversight, by design
        </div>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">Real tenants stay in shadow mode until certified on their own reviewed tickets.</p>
      </div>
    </>
  );

  return (
    <div className="min-h-dvh">
      <div className="atmosphere" aria-hidden="true" />
      <aside aria-label="Sidebar" className="glass fixed inset-y-3 left-3 z-30 hidden w-[264px] flex-col rounded-3xl p-4 lg:flex">{sidebar(false)}</aside>

      <AnimatePresence>
        {open ? (
          <>
            <motion.div
              key="scrim"
              className="fixed inset-0 z-40 bg-black/40 lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              key="drawer"
              id="mobile-menu"
              ref={drawerRef}
              role="dialog"
              aria-modal="true"
              aria-label="Menu"
              className="glass-strong fixed inset-y-2 left-2 z-50 flex w-[min(300px,calc(100vw-16px))] flex-col rounded-3xl p-4 lg:hidden"
              initial={{ x: -320 }}
              animate={{ x: 0 }}
              exit={{ x: -320 }}
              transition={{ type: "spring", stiffness: 380, damping: 36 }}
            >
              {sidebar(true)}
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>

      <div inert={open} className="lg:pl-[284px]">
        <header className="sticky top-0 z-20 px-3 pt-3 sm:px-5">
          <div className="glass flex min-h-14 items-center gap-2 rounded-2xl px-2 sm:gap-3 sm:px-3">
            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-label="Open menu"
              aria-expanded={open}
              aria-controls="mobile-menu"
              className="grid size-11 place-items-center rounded-xl lg:hidden"
            >
              <Menu aria-hidden="true" className="size-5" />
            </button>
            <Link href="/" aria-label="ResolveIT home" className="grid size-11 place-items-center lg:hidden">
              <MonolithMark size={26} />
            </Link>
            <p className="min-w-0 flex-1 truncate text-sm">
              <span className="hidden text-muted-foreground sm:inline">ResolveIT </span>
              <span aria-hidden="true" className="hidden px-1.5 text-muted-foreground sm:inline">/</span>
              <span className="font-semibold">{current?.label ?? "Workspace"}</span>
            </p>
            <EngineStatus />
            <ThemeToggle className="hidden sm:inline-flex" />
            {identity ? (
              <>
                <span className="hidden items-center gap-1.5 rounded-full border bg-card/60 px-3 py-1.5 text-xs font-semibold capitalize xl:inline-flex">
                  {identity.role}
                  {identity.is_synthetic ? <span className="font-normal text-muted-foreground"> · demo tenant</span> : null}
                </span>
                <button type="button" onClick={() => void signOut()} className="inline-flex min-h-10 items-center gap-1.5 rounded-xl px-2.5 text-sm font-medium text-muted-foreground hover:text-foreground">
                  <LogOut aria-hidden="true" className="size-4" />
                  <span className="hidden sm:inline">Sign out</span>
                  <span className="sr-only sm:hidden">Sign out</span>
                </button>
              </>
            ) : identity === null ? (
              <Link href="/login" className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-foreground px-3 text-sm font-semibold text-background">
                <LogIn aria-hidden="true" className="size-4" />
                Sign in
              </Link>
            ) : null}
          </div>
        </header>
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1480px] px-3 pb-16 pt-6 outline-none sm:px-5 lg:pt-8">
          {children}
        </main>
        <footer className="mx-auto flex max-w-[1480px] flex-wrap items-center justify-between gap-3 border-t px-5 py-6 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-2">
            <MonolithMark size={16} /> Every decision carries its evidence.
          </span>
          <span>
            English · <span lang="hi">हिन्दी</span> · Hinglish
          </span>
          <ThemeToggle className="sm:hidden" />
        </footer>
      </div>
    </div>
  );
}
