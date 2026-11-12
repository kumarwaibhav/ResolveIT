import { apiFetch, relay } from "@/lib/server-api";

export async function POST(request: Request): Promise<Response> {
  return relay(await apiFetch("/v1/incidents", { method: "POST", body: await request.text() }));
}
