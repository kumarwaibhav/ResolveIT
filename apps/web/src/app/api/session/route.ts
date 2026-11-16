import { NextRequest, NextResponse } from "next/server";
import { openSession, sealSession, SESSION_COOKIE, SESSION_TTL_SECONDS } from "@/lib/auth-session";

export async function POST(request: NextRequest) {
  if (Number(request.headers.get("content-length") ?? 0) > 2048) {
    return NextResponse.json({ detail: "Request too large" }, { status: 413 });
  }
  let apiKey: unknown;
  const reader = request.body?.getReader();
  if (!reader) return NextResponse.json({ detail: "JSON body required" }, { status: 400 });
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const part = await reader.read();
    if (part.done) break;
    size += part.value.byteLength;
    if (size > 2048) {
      await reader.cancel();
      return NextResponse.json({ detail: "Request too large" }, { status: 413 });
    }
    chunks.push(part.value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { apiKey = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)).apiKey; } catch {
    return NextResponse.json({ detail: "Invalid JSON" }, { status: 400 });
  }
  if (typeof apiKey !== "string" || !apiKey || apiKey.length > 512) {
    return NextResponse.json({ detail: "Valid API credential required" }, { status: 400 });
  }
  const base = process.env.RESOLVEIT_API_URL;
  if (!base) return NextResponse.json({ detail: "API unavailable" }, { status: 503 });
  const identity = await fetch(`${base}/v1/me`, { cache: "no-store", headers: { authorization: `Bearer ${apiKey}` } });
  if (!identity.ok) return NextResponse.json({ detail: "Credential rejected" }, { status: 401 });
  const me = await identity.json();
  let sealed: string;
  try { sealed = await sealSession(apiKey); } catch {
    return NextResponse.json({ detail: "Session service is not configured" }, { status: 503 });
  }
  const response = NextResponse.json({ tenant_id: me.tenant_id, role: me.role, human_labeling_enrolled: me.human_labeling_enrolled });
  response.cookies.set(SESSION_COOKIE, sealed, { httpOnly: true, secure: process.env.RESOLVEIT_LOCAL_DEMO !== "true", sameSite: "strict", path: "/", maxAge: SESSION_TTL_SECONDS });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
export async function GET(request: NextRequest) {
  const apiKey = await openSession(request.cookies.get(SESSION_COOKIE)?.value);
  return NextResponse.json({ signed_in: apiKey !== null }, { headers: { "Cache-Control": "no-store" } });
}
export async function DELETE() {
  const response = NextResponse.json({ signed_in: false });
  response.cookies.set(SESSION_COOKIE, "", { httpOnly: true, secure: process.env.RESOLVEIT_LOCAL_DEMO !== "true", sameSite: "strict", path: "/", maxAge: 0 });
  return response;
}
