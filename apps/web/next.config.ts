import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  experimental: { cpus: 1, webpackBuildWorker: false, webpackMemoryOptimizations: true },
  // Every route, /login included (audit finding L3). Script sources are not restricted here:
  // Next.js inline bootstrap scripts would need per-request nonces; framing, base URI, form
  // targets and plugins are locked down, and HSTS applies outside the loopback demo.
  async headers() {
    const security = [
      { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "same-origin" },
      { key: "Permissions-Policy", value: "camera=(), geolocation=(), microphone=(self)" },
    ];
    if (process.env.RESOLVEIT_LOCAL_DEMO !== "true") {
      security.push({ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" });
    }
    return [{ source: "/:path*", headers: security }];
  },
};

export default config;
