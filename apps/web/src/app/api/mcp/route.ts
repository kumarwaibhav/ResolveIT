import { apiFetch } from "@/lib/server-api";

const VERSION = "2026-07-28";

/**
 * Forwards one JSON-RPC message to the MCP endpoint as the demo agent and returns
 * what was sent and what came back, so the simulator can show both. The bearer
 * token is added here and is never echoed.
 */
export async function POST(request: Request): Promise<Response> {
  const message = (await request.json()) as { method?: unknown; params?: { name?: unknown } };
  if (typeof message.method !== "string") {
    return Response.json({ detail: "method is required" }, { status: 400 });
  }
  const headers: Record<string, string> = { "MCP-Protocol-Version": VERSION, "Mcp-Method": message.method };
  if (typeof message.params?.name === "string") headers["Mcp-Name"] = message.params.name;
  const upstream = await apiFetch("/mcp", { method: "POST", agent: true, headers, body: JSON.stringify(message) });
  return Response.json({
    request: { headers: { ...headers, Authorization: "Bearer (agent key, held on the server)" }, body: message },
    status: upstream.status,
    response: await upstream.json(),
  });
}
