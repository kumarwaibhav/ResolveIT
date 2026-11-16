import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { openSession, sealSession, SESSION_TTL_SECONDS } from "@/lib/auth-session";

describe("encrypted credential sessions", () => {
  const original = process.env.RESOLVEIT_SESSION_KEY_B64;
  beforeEach(() => { process.env.RESOLVEIT_SESSION_KEY_B64 = btoa("k".repeat(32)); });
  afterEach(() => { if (original === undefined) delete process.env.RESOLVEIT_SESSION_KEY_B64; else process.env.RESOLVEIT_SESSION_KEY_B64 = original; });
  it("round trips without exposing credentials", async () => {
    const token = await sealSession("private-credential", 1000);
    expect(token).not.toContain("private-credential");
    expect(await openSession(token, 1001)).toBe("private-credential");
  });
  it("uses a fresh nonce for every session", async () => {
    expect(await sealSession("same", 1000)).not.toBe(await sealSession("same", 1000));
  });
  it("rejects expiry at exact boundary", async () => {
    const token = await sealSession("private", 1000);
    expect(await openSession(token, 1000 + SESSION_TTL_SECONDS * 1000)).toBeNull();
  });
  it("rejects tampering, invalid input, and wrong key", async () => {
    const token = await sealSession("private", 1000);
    const [nonce, body = ""] = token.split(".");
    expect(await openSession(`${nonce}.${body[0] === "A" ? "B" : "A"}${body.slice(1)}`, 1001)).toBeNull();
    expect(await openSession("bad", 1001)).toBeNull();
    process.env.RESOLVEIT_SESSION_KEY_B64 = btoa("x".repeat(32));
    expect(await openSession(token, 1001)).toBeNull();
  });
  it("fails closed without configuration", async () => {
    delete process.env.RESOLVEIT_SESSION_KEY_B64;
    await expect(sealSession("private")).rejects.toThrow("not configured");
    expect(await openSession("bad")).toBeNull();
  });
});
