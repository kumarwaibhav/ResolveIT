"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Incident intake", code: "01", detail: "Understand & route" },
  { href: "/review", label: "Review console", code: "02", detail: "Human judgment" },
  { href: "/bounce", label: "Bounce analyzer", code: "03", detail: "Follow the handoffs" },
  { href: "/evaluation", label: "Evaluation lab", code: "04", detail: "Evidence over confidence" },
  { href: "/mcp", label: "Agent handoff", code: "05", detail: "Inspect every exchange" },
  { href: "/settings", label: "Tenant settings", code: "06", detail: "Control & privacy" },
];

export function SiteNav() {
  const path = usePathname();
  return (
    <aside className="workspace-sidebar">
        <Link href="/" className="brand-lockup" aria-label="ResolveIT home"><span className="brand-mark" aria-hidden="true">r<span>↗</span></span><span>resolve<span className="brand-it">it</span><small>INCIDENT INTELLIGENCE</small></span></Link>
        <div className="tenant-switch"><span className="tenant-avatar">R</span><div>ResolveIT sandbox<small>Local workspace</small></div><span aria-hidden="true">⌄</span></div>
        <p className="nav-eyebrow">WORKSPACE</p>
        <nav aria-label="Main">
          <ul className="workspace-links">
            {LINKS.map((link) => {
              const current = link.href === "/" ? path === "/" || path.startsWith("/incidents") : path.startsWith(link.href);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    aria-current={current ? "page" : undefined}
                    className={current ? "workspace-link is-active" : "workspace-link"}
                  >
                    <span className="nav-code">{link.code}</span><span>{link.label}<small>{link.detail}</small></span>{current && <span className="nav-active-dot" aria-hidden="true" />}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      <div className="sidebar-footer"><span className="status-dot" aria-hidden="true" /><div>Human oversight, by design<small>Real tenants stay in shadow mode</small></div><span className="sidebar-version">0.1</span></div>
    </aside>
  );
}
