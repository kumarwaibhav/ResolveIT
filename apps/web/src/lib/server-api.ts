import "server-only";
import { cookies } from "next/headers";
import { openSession, SESSION_COOKIE } from "@/lib/auth-session";

/** Server-side calls to the ResolveIT API. Keys stay on the server; the browser never sees them. */
function env(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing environment variable ${name}`);
  return value;
}

export async function apiFetch(path: string, init: RequestInit & { agent?: boolean } = {}): Promise<Response> {
  const { agent, headers, ...rest } = init;
  const sessionKey = await openSession((await cookies()).get(SESSION_COOKIE)?.value);
  let key = sessionKey;
  if (!key && process.env.RESOLVEIT_LOCAL_DEMO === "true") {
    key = env(agent ? "RESOLVEIT_AGENT_KEY" : "RESOLVEIT_API_KEY");
    const identity = await fetch(`${env("RESOLVEIT_API_URL")}/v1/me`, {
      cache: "no-store", headers: { authorization: `Bearer ${key}` },
    });
    if (!identity.ok || (await identity.json()).is_synthetic !== true) {
      return Response.json({ detail: "Local shared-key mode requires a verified synthetic tenant" }, { status: 403 });
    }
  }
  if (!key) return Response.json({ detail: "Sign in required" }, { status: 401 });
  return fetch(`${env("RESOLVEIT_API_URL")}${path}`, {
    ...rest,
    cache: "no-store",
    headers: { "content-type": "application/json", ...headers, authorization: `Bearer ${key}` },
  });
}

/** Pass the upstream status and JSON body through unchanged. */
export async function relay(upstream: Response): Promise<Response> {
  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
}

export const isUuid = (value: string): boolean =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
