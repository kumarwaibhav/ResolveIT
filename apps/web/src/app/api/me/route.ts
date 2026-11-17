import { apiFetch } from "@/lib/server-api";

/** Who is signed in: tenant, role and whether the tenant is the synthetic demo. No secrets. */
export async function GET(): Promise<Response> {
  const upstream = await apiFetch("/v1/me");
  if (!upstream.ok) return Response.json({ detail: "Not signed in" }, { status: upstream.status === 403 ? 403 : 401 });
  const me = (await upstream.json()) as { tenant_id?: unknown; role?: unknown; is_synthetic?: unknown };
  return Response.json(
    { tenant_id: String(me.tenant_id ?? ""), role: String(me.role ?? ""), is_synthetic: me.is_synthetic === true },
    { headers: { "Cache-Control": "no-store" } },
  );
}
