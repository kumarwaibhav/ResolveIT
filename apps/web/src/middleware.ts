import { NextRequest, NextResponse } from "next/server";
import { openSession, SESSION_COOKIE } from "@/lib/auth-session";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/** Shared server keys are permitted only in an explicitly enabled local demo.
 * Production sessions must replace this gate before public deployment.
 */
export async function middleware(request: NextRequest) {
  let host: string;
  try {
    host = new URL(`http://${request.headers.get("host") ?? ""}`).hostname;
  } catch {
    return NextResponse.json({ detail: "Invalid host" }, { status: 400 });
  }
  const demo = process.env.RESOLVEIT_LOCAL_DEMO === "true";
  if (demo && !LOCAL_HOSTS.has(host)) {
    return NextResponse.json(
      { detail: "Local demo requires loopback host" }, { status: 403 },
    );
  }
  const publicOrigin = process.env.RESOLVEIT_PUBLIC_ORIGIN;
  if (!demo) {
    try {
      if (!publicOrigin || new URL(publicOrigin).protocol !== "https:" || new URL(publicOrigin).host !== request.headers.get("host")) {
        return NextResponse.json({ detail: "HTTPS public origin must be configured" }, { status: 503 });
      }
    } catch { return NextResponse.json({ detail: "Invalid public origin" }, { status: 503 }); }
  }
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite === "cross-site") {
    return NextResponse.json({ detail: "Cross-site request denied" }, { status: 403 });
  }
  if (origin) {
    try {
      const parsed = new URL(origin);
      const expectedOrigin = demo
        ? new URL(`${request.nextUrl.protocol}//${request.headers.get("host")}`).origin
        : new URL(publicOrigin!).origin;
      if (parsed.origin !== expectedOrigin) {
        return NextResponse.json({ detail: "Origin denied" }, { status: 403 });
      }
    } catch {
      return NextResponse.json({ detail: "Invalid origin" }, { status: 403 });
    }
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(request.method) && !origin) {
    return NextResponse.json({ detail: "Same-origin browser action required" }, { status: 403 });
  }
  if (!demo && request.nextUrl.pathname !== "/api/session" && request.nextUrl.pathname !== "/login") {
    const credential = await openSession(request.cookies.get(SESSION_COOKIE)?.value);
    if (!credential) {
      if (request.nextUrl.pathname.startsWith("/api/")) {
        return NextResponse.json({ detail: "Sign in required" }, { status: 401 });
      }
      return NextResponse.redirect(new URL("/login", request.url));
    }
  }
  const response = NextResponse.next();
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "same-origin");
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export const config = { matcher: ["/", "/login", "/api/:path*", "/incidents/:path*", "/review/:path*", "/bounce/:path*", "/evaluation/:path*", "/settings/:path*", "/mcp/:path*"] };
