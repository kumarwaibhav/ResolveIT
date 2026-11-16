import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  experimental: { cpus: 1, webpackBuildWorker: false, webpackMemoryOptimizations: true },
};

export default config;
