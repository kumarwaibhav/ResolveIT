import { apiFetch, relay } from "@/lib/server-api";
import { boundedBody } from "@/lib/bounded-body";

type Context = { params: Promise<{ path: string[] }> };
const uuid = "[0-9a-fA-F-]{36}";
async function forward(request: Request, context: Context): Promise<Response> {
  const { path } = await context.params;
  const route = path.join("/");
  const allowed = request.method === "GET" ? /^(review(?:\/(?:agreement|export))?|settings|evaluation)$/ : request.method === "PUT" ? /^settings$/ : new RegExp(`^(review/${uuid}/(?:labels|adjudication)|bounce/analyze)$`);
  if (!allowed.test(route)) return Response.json({ detail: "Unknown workspace operation" }, { status: 404 });
  const query = new URL(request.url).searchParams;
  const params = new URLSearchParams();
  for (const key of ["blind", "limit", "after"]) { const value = query.get(key); if (value !== null) params.set(key, value); }
  const suffix = params.size ? `?${params}` : "";
  const body = request.method === "GET" ? undefined : await boundedBody(request, route === "bounce/analyze" ? 8 * 1024 * 1024 : 128 * 1024);
  if (body instanceof Response) return body;
  return relay(await apiFetch(`/v1/${route}${suffix}`, { method: request.method, body }));
}
export const GET = forward;
export const POST = forward;
export const PUT = forward;
