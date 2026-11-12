import { apiFetch, isUuid, relay } from "@/lib/server-api";

export async function GET(_: Request, ctx: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await ctx.params;
  if (!isUuid(id)) return Response.json({ detail: "incident not found" }, { status: 404 });
  return relay(await apiFetch(`/v1/incidents/${id}`));
}
