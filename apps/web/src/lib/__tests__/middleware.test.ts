import { afterEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "@/middleware";

const previous = { demo: process.env.RESOLVEIT_LOCAL_DEMO, origin: process.env.RESOLVEIT_PUBLIC_ORIGIN };
afterEach(() => {
  if (previous.demo === undefined) delete process.env.RESOLVEIT_LOCAL_DEMO; else process.env.RESOLVEIT_LOCAL_DEMO = previous.demo;
  if (previous.origin === undefined) delete process.env.RESOLVEIT_PUBLIC_ORIGIN; else process.env.RESOLVEIT_PUBLIC_ORIGIN = previous.origin;
});
describe("browser authorization boundary", () => {
  it("uses validated loopback Host when production Next has an internal hostname", async () => {
    process.env.RESOLVEIT_LOCAL_DEMO = "true";
    const result = await middleware(new NextRequest("http://localhost:3000/api/incidents", {
      method: "POST", headers: { host: "127.0.0.1:3000", origin: "http://127.0.0.1:3000" },
    }));
    expect(result.status).toBe(200);
    const denied = await middleware(new NextRequest("http://localhost:3000/api/incidents", {
      method: "POST", headers: { host: "127.0.0.1:3000", origin: "http://localhost:3000" },
    }));
    expect(denied.status).toBe(403);
  });
  it("denies remote hosts in demo mode", async () => {
    process.env.RESOLVEIT_LOCAL_DEMO = "true";
    const result = await middleware(new NextRequest("http://evil.example/api/incidents", { headers: { host: "evil.example" } }));
    expect(result.status).toBe(403);
  });
  it("denies missing and cross-site mutation origins", async () => {
    process.env.RESOLVEIT_LOCAL_DEMO = "true";
    const extras: Record<string, string>[] = [{}, { origin: "https://evil.example" }, { "sec-fetch-site": "cross-site" }];
    for (const extra of extras) {
      const result = await middleware(new NextRequest("http://localhost:3000/api/session", {
        method: "POST", headers: { host: "localhost:3000", ...extra },
      }));
      expect(result.status).toBe(403);
    }
  });
  it("allows local same-origin demo requests", async () => {
    process.env.RESOLVEIT_LOCAL_DEMO = "true";
    const result = await middleware(new NextRequest("http://localhost:3000/api/session", {
      method: "POST", headers: { host: "localhost:3000", origin: "http://localhost:3000" },
    }));
    expect(result.status).toBe(200);
  });
  it("denies anonymous production API access", async () => {
    delete process.env.RESOLVEIT_LOCAL_DEMO;
    process.env.RESOLVEIT_PUBLIC_ORIGIN = "https://resolve.example";
    const result = await middleware(new NextRequest("https://resolve.example/api/incidents", { headers: { host: "resolve.example" } }));
    expect(result.status).toBe(401);
  });
  it("serves the production sign-in page with security headers but redirects other pages", async () => {
    delete process.env.RESOLVEIT_LOCAL_DEMO;
    process.env.RESOLVEIT_PUBLIC_ORIGIN = "https://resolve.example";
    const login = await middleware(new NextRequest("https://resolve.example/login", { headers: { host: "resolve.example" } }));
    expect(login.status).toBe(200);
    expect(login.headers.get("x-frame-options")).toBe("DENY");
    const home = await middleware(new NextRequest("https://resolve.example/", { headers: { host: "resolve.example" } }));
    expect(home.status).toBe(307);
    expect(home.headers.get("location")).toBe("https://resolve.example/login");
  });
});
