/** Encrypted stateless credential session. API verifies credential on every call.
 * A fresh random nonce prevents GCM nonce reuse; payload has a fixed expiry.
 * Use a dedicated 32-byte base64 key, separate from incident encryption keys.
 */
export const SESSION_COOKIE = process.env.RESOLVEIT_LOCAL_DEMO === "true"
  ? "resolveit_local_session" : "__Host-resolveit_session";
export const SESSION_TTL_SECONDS = 3600;
const encoder = new TextEncoder();
const aad = encoder.encode("resolveit:web-session:v1");

function decode(value: string): Uint8Array<ArrayBuffer> {
  return Uint8Array.from(atob(value.replaceAll("-", "+").replaceAll("_", "/")), (c) => c.charCodeAt(0));
}
function encode(value: Uint8Array): string {
  return btoa(String.fromCharCode(...value)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}
async function key(): Promise<CryptoKey> {
  const value = process.env.RESOLVEIT_SESSION_KEY_B64;
  if (!value) throw new Error("Session key is not configured");
  const bytes = decode(value);
  if (bytes.length !== 32) throw new Error("Session key must be 32 bytes");
  return crypto.subtle.importKey("raw", bytes, "AES-GCM", false, ["encrypt", "decrypt"]);
}
export async function sealSession(apiKey: string, now = Date.now()): Promise<string> {
  if (!apiKey || apiKey.length > 512) throw new Error("Invalid credential length");
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const body = encoder.encode(JSON.stringify({ apiKey, expires: now + SESSION_TTL_SECONDS * 1000 }));
  const cipher = await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce, additionalData: aad }, await key(), body);
  return `${encode(nonce)}.${encode(new Uint8Array(cipher))}`;
}
export async function openSession(token: string | undefined, now = Date.now()): Promise<string | null> {
  if (!token || token.length > 2048) return null;
  try {
    const parts = token.split(".");
    if (parts.length !== 2) return null;
    const [noncePart, cipherPart] = parts;
    if (!noncePart || !cipherPart) return null;
    const nonce = decode(noncePart);
    if (nonce.length !== 12) return null;
    const plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: nonce, additionalData: aad }, await key(), decode(cipherPart),
    );
    const payload: unknown = JSON.parse(new TextDecoder().decode(plain));
    if (typeof payload !== "object" || payload === null) return null;
    const value = payload as { apiKey?: unknown; expires?: unknown };
    if (typeof value.apiKey !== "string" || !value.apiKey || value.apiKey.length > 512 ||
      typeof value.expires !== "number" || !Number.isFinite(value.expires) ||
      value.expires <= now || value.expires > now + SESSION_TTL_SECONDS * 1000) return null;
    return value.apiKey;
  } catch { return null; }
}
