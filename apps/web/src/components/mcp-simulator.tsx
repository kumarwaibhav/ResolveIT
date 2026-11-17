"use client";

import { PageGuide } from "@/components/page-guide";
import { Check, Copy, Network, PlugZap, Send } from "lucide-react";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/motion";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { WorkspaceHeading } from "@/components/workspace-heading";

interface Exchange {
  request: { headers: Record<string, string>; body: unknown };
  status: number;
  response: {
    result?: {
      resultType?: "complete" | "input_required";
      requestState?: string;
      inputRequests?: Record<string, { params: { message: string; requestedSchema: { properties: { answer: { enum: string[] } } } } }>;
      content?: { text: string }[];
    };
    error?: { code: number; message: string };
  };
}

const META = {
  "io.modelcontextprotocol/protocolVersion": "2026-07-28",
  "io.modelcontextprotocol/clientInfo": { name: "resolveit-simulator", version: "0.1.0" },
  "io.modelcontextprotocol/clientCapabilities": { elicitation: {} },
};

async function exchange(message: unknown): Promise<Exchange> {
  const res = await fetch("/api/mcp", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(message) });
  if (!res.ok) throw new Error(`The simulator proxy returned ${res.status}.`);
  return (await res.json()) as Exchange;
}

const TOKEN = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

function highlight(source: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let i = 0;
  for (const m of source.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    if (at > last) out.push(source.slice(last, at));
    const cls = m[1] ? (m[2] ? "json-key" : "json-string") : m[3] ? "json-literal" : "json-number";
    out.push(<span key={i++} className={cls}>{m[1] ?? m[0]}</span>);
    if (m[2]) out.push(m[2]);
    last = at + m[0].length;
  }
  out.push(source.slice(last));
  return out;
}

function Json({ label, value }: { label: string; value: unknown }) {
  const text = JSON.stringify(value, null, 2);
  const [copied, setCopied] = useState(false);
  return (
    <div className="min-w-0 overflow-hidden rounded-2xl border bg-card">
      <div className="flex items-center justify-between gap-2 border-b px-4 py-2">
        <p className="font-mono text-[11px] font-medium text-muted-foreground">{label}</p>
        <button
          type="button"
          aria-label={`${copied ? "Copied" : "Copy"} ${label}`}
          onClick={() => void navigator.clipboard?.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}
          className="inline-flex min-h-8 items-center gap-1 rounded-md px-2 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          {copied ? <Check aria-hidden="true" className="size-3.5" /> : <Copy aria-hidden="true" className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre tabIndex={0} aria-label={label} className="max-h-80 overflow-auto p-4 font-mono text-[12px] leading-5">{highlight(text)}</pre>
    </div>
  );
}

export function McpSimulator() {
  const [text, setText] = useState("it stopped working this morning, the v-p-n client shows nothing");
  const [trips, setTrips] = useState<Exchange[]>([]);
  const [answer, setAnswer] = useState("unknown");
  const [quote, setQuote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [standard, setStandard] = useState<Exchange | null>(null);

  const last = trips.at(-1)?.response.result;
  const pending = last?.resultType === "input_required" ? last : null;
  const ask = pending?.inputRequests?.clarify?.params;

  const call = async (extra: Record<string, unknown>, fresh: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const message = {
        jsonrpc: "2.0",
        id: fresh ? 1 : trips.length + 1,
        method: "tools/call",
        params: { name: "submit_incident", arguments: { text }, _meta: META, ...extra },
      };
      const result = await exchange(message);
      setTrips((prev) => (fresh ? [result] : [...prev, result]));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const reply = (inputResponse: unknown) =>
    void call({ requestState: pending?.requestState, inputResponses: { clarify: inputResponse } }, false);

  return (
    <div className="space-y-6">
      <WorkspaceHeading eyebrow="05 · Agent hand-off" title="Trust the trace." description="AI agents can file tickets through the Model Context Protocol (MCP). Watch every request and response, and see how an agent must quote the user before its answer counts." /><PageGuide page="mcp" />
      <section className="surface-panel"><div className="flex items-start gap-3"><span aria-hidden="true" className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent text-signal"><PlugZap className="size-5" /></span><div><p className="eyebrow !mb-1">Standard MCP · 2025-11-25</p><h2 className="panel-title">Connect like any MCP client</h2><p className="panel-copy">See the handshake and the tool list a standard client receives. The adapter is stateless and issues no session ID.</p></div></div><div className="action-row"><button className="workspace-button" disabled={busy} onClick={async () => { setBusy(true); setError(null); try { setStandard(await exchange({ jsonrpc: "2.0", id: "init", method: "initialize", params: { protocolVersion: "2025-11-25", capabilities: {}, clientInfo: { name: "resolveit-inspector", version: "0.1.0" } } })); } catch (err) { setError(err instanceof Error ? err.message : "Initialization failed."); } finally { setBusy(false); } }}>Inspect initialize</button><button className="workspace-button" disabled={busy} onClick={async () => { setBusy(true); setError(null); try { setStandard(await exchange({ jsonrpc: "2.0", id: "tools", method: "tools/list", params: {} })); } catch (err) { setError(err instanceof Error ? err.message : "Discovery failed."); } finally { setBusy(false); } }}>Inspect tools/list</button></div>{standard && <div className="mt-5 grid gap-4 md:grid-cols-2"><Json label="Standard request" value={standard.request} /><Json label={`Standard response (HTTP ${standard.status})`} value={standard.response} /></div>}</section>
      <div className="flex items-start gap-3 pt-4"><span aria-hidden="true" className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent text-signal"><Network className="size-5" /></span><div><p className="eyebrow !mb-1">ResolveIT enterprise profile · 2026-07-28</p><h2 className="panel-title">Signed clarification round trips</h2><p className="panel-copy">An opt-in profile: the server signs its request state, and an agent may answer a question only by quoting the user&apos;s own words.</p></div></div>
      <form
        className="surface-panel space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) void call({}, true);
        }}
      >
        <Label htmlFor="agent-text">The user&apos;s report, verbatim</Label>
        <Textarea id="agent-text" value={text} maxLength={20_000} rows={3} onChange={(e) => setText(e.target.value)} className="rounded-xl bg-card font-mono text-sm" />
        <Button type="submit" disabled={busy || !text.trim()} className="min-h-11 gap-2 px-5">
          <Send aria-hidden="true" className="size-4" />
          Call submit_incident
        </Button>
        {error ? <p role="alert" className="text-sm text-risk">{error}</p> : null}
      </form>

      <ol className="space-y-4" aria-live="polite">
        {trips.map((trip, i) => (
          <li key={i}>
            <Reveal className="surface-panel">
              <div className="mb-4 flex items-center gap-3">
                <span aria-hidden="true" className="grid size-8 place-items-center rounded-full bg-foreground font-mono text-xs font-bold text-background">{i + 1}</span>
                <h3 className="text-sm font-semibold">
                  Round trip {i + 1}:{" "}
                  {trip.response.error
                    ? `error ${trip.response.error.code}`
                    : trip.response.result?.resultType === "input_required"
                      ? "the server needs one answer"
                      : "complete"}
                </h3>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <Json label="Request" value={trip.request} />
                <Json label={`Response (HTTP ${trip.status})`} value={trip.response} />
              </div>
            </Reveal>
          </li>
        ))}
      </ol>

      {pending && ask ? (
        <form
          className="space-y-4 rounded-2xl border border-signal/30 bg-accent/50 p-5"
          onSubmit={(e) => {
            e.preventDefault();
            reply({ action: "accept", content: quote.trim() ? { answer, evidence_quote: quote } : { answer } });
          }}
        >
          <div>
            <h2 className="text-base font-medium">{ask.message}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              An answer only counts if it quotes the user&apos;s own words. Without a matching quote it is recorded as
              unknown.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="agent-answer">Answer</Label>
              <select
                id="agent-answer"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                className="field-input"
              >
                {ask.requestedSchema.properties.answer.enum.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent-quote">Quote from the report</Label>
              <input
                id="agent-quote"
                value={quote}
                onChange={(e) => setQuote(e.target.value)}
                placeholder="v-p-n client"
                className="field-input"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={busy} className="min-h-11 px-5">Retry with answer</Button>
            <Button type="button" variant="outline" disabled={busy} onClick={() => reply({ action: "decline" })} className="min-h-11 px-5">
              Decline
            </Button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
