import { apiFetch, isUuid, relay } from "@/lib/server-api";
import { boundedBody } from "@/lib/bounded-body";

export async function POST(request: Request, ctx: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await ctx.params;
  if (!isUuid(id)) return Response.json({ detail: "incident not found" }, { status: 404 });
  const body = await boundedBody(request);
  if (body instanceof Response) return body;
  return relay(await apiFetch(`/v1/incidents/${id}/answer`, { method: "POST", body }));
}
