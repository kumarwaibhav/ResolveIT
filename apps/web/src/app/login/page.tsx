"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [apiKey, setApiKey] = useState(""), [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const router = useRouter();
  return <section className="surface-panel mx-auto max-w-lg">
    <p className="eyebrow">RESOLVEIT / SECURE ACCESS</p><h1 className="panel-title">Your workspace. Your identity.</h1>
    <p className="panel-copy mt-3">Sign in with your organization’s individual API credential. Permissions and review identity follow your credential.</p>
    <form className="mt-6" onSubmit={async (event) => {
      event.preventDefault(); setBusy(true); setMessage("");
      try {
        const response = await fetch("/api/session", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ apiKey }) });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail ?? "Sign-in failed");
        setApiKey(""); router.replace("/review"); router.refresh();
      } catch (error) { setMessage(error instanceof Error ? error.message : "Sign-in failed"); } finally { setBusy(false); }
    }}>
      <label className="field-label" htmlFor="api-credential">Individual API credential</label>
      <input id="api-credential" className="field-input" type="password" autoComplete="current-password" maxLength={512} required value={apiKey} onChange={(event) => setApiKey(event.target.value)} />
      <button className="workspace-button primary mt-5" disabled={busy || !apiKey}>{busy ? "Signing in…" : "Sign in"}</button>
    </form>
    <button className="workspace-button mt-3" onClick={async () => {
      const result = await fetch("/api/session", { method: "DELETE" });
      if (result.ok) { setMessage("Signed out. Session cleared."); router.refresh(); }
    }}>Clear current session</button>
    {message && <p role="status" className="panel-copy mt-4">{message}</p>}
  </section>;
}
