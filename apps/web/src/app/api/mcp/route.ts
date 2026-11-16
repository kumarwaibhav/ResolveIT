import { apiFetch } from "@/lib/server-api";
import { boundedBody } from "@/lib/bounded-body";

const STANDARD_VERSION = "2025-11-25";
const ENTERPRISE_VERSION = "2026-07-28";

/**
 * Forwards one JSON-RPC message to the MCP endpoint as the demo agent and returns
 * what was sent and what came back, so the simulator can show both. The bearer
 * token is added here and is never echoed.
 */
export async function POST(request: Request): Promise<Response> {
  let message: { method?: unknown; params?: { name?: unknown; _meta?: Record<string, unknown> } };
  const body = await boundedBody(request);
  if (body instanceof Response) return body;
  try { message = JSON.parse(body); } catch { return Response.json({ detail: "Invalid JSON" }, { status: 400 }); }
  if (!message || typeof message !== "object") return Response.json({ detail: "JSON-RPC object required" }, { status: 400 });
  if (typeof message.method !== "string") {
    return Response.json({ detail: "method is required" }, { status: 400 });
  }
  const enterprise = message.params?._meta?.["io.modelcontextprotocol/protocolVersion"] === ENTERPRISE_VERSION;
  const headers: Record<string, string> = { "MCP-Protocol-Version": enterprise ? ENTERPRISE_VERSION : STANDARD_VERSION };
  if (enterprise) headers["Mcp-Method"] = message.method;
  if (typeof message.params?.name === "string") headers["Mcp-Name"] = message.params.name;
  const upstream = await apiFetch("/mcp", { method: "POST", agent: true, headers, body: JSON.stringify(message) });
  return Response.json({
    request: { headers: { ...headers, Authorization: "Bearer (agent key, held on the server)" }, body: message },
    status: upstream.status,
    response: upstream.status === 202 ? null : await upstream.json(),
  });
}
