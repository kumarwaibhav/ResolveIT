import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { SiteNav } from "@/components/site-nav";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "ResolveIT", template: "%s · ResolveIT" },
  description: "Report an IT problem and see how it is understood and routed.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-10 focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <SiteNav />
        <div className="workspace-content">
          <header className="workspace-topbar"><span>ResolveIT AI <span aria-hidden="true">/</span> Workspace</span><span className="topbar-badge">CONTROLLED SANDBOX</span></header>
          <main id="main" className="workspace-main">{children}</main>
          <footer className="workspace-footer"><span>Every decision should have evidence.</span><span>English · हिन्दी · Hinglish</span></footer>
        </div>
      </body>
    </html>
  );
}
