"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Report a problem" },
  { href: "/mcp", label: "Agent hand-off" },
];

export function SiteNav() {
  const path = usePathname();
  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-base font-semibold tracking-tight">ResolveIT</Link>
        <nav aria-label="Main">
          <ul className="flex gap-1">
            {LINKS.map((link) => {
              const current = link.href === "/" ? path === "/" || path.startsWith("/incidents") : path.startsWith(link.href);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    aria-current={current ? "page" : undefined}
                    className={cn(
                      "inline-flex min-h-11 items-center rounded-md px-3 text-sm sm:min-h-9",
                      current ? "bg-secondary font-medium" : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {link.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
