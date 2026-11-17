/** Engine reachability for the status chip. The API's /healthz is public; nothing sensitive is returned. */
export async function GET(): Promise<Response> {
  const base = process.env.RESOLVEIT_API_URL;
  if (!base) return Response.json({ ok: false }, { status: 503 });
  try {
    const res = await fetch(`${base}/healthz`, { cache: "no-store", signal: AbortSignal.timeout(2500) });
    return Response.json({ ok: res.ok }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ ok: false }, { headers: { "Cache-Control": "no-store" } });
  }
}
