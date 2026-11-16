/** Enforce actual bytes before JSON parsing, including chunked requests. */
export async function boundedBody(request: Request, limit = 128 * 1024): Promise<string | Response> {
  const reader = request.body?.getReader();
  if (!reader) return "";
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const part = await reader.read();
    if (part.done) break;
    size += part.value.byteLength;
    if (size > limit) {
      await reader.cancel();
      return Response.json({ detail: "Request too large" }, { status: 413 });
    }
    chunks.push(part.value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { return new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
  catch { return Response.json({ detail: "Invalid UTF-8" }, { status: 400 }); }
}
