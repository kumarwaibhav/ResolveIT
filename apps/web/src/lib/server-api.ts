import "server-only";

/** Server-side calls to the ResolveIT API. Keys stay on the server; the browser never sees them. */
function env(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing environment variable ${name}`);
  return value;
}

export async function apiFetch(path: string, init: RequestInit & { agent?: boolean } = {}): Promise<Response> {
  const { agent, headers, ...rest } = init;
  const key = env(agent ? "RESOLVEIT_AGENT_KEY" : "RESOLVEIT_API_KEY");
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
