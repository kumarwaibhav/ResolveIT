import { apiFetch, relay } from "@/lib/server-api";
import { boundedBody } from "@/lib/bounded-body";

export async function POST(request: Request): Promise<Response> {
  const body = await boundedBody(request);
  if (body instanceof Response) return body;
  return relay(await apiFetch("/v1/privacy/erasure", { method: "POST", body }));
}
