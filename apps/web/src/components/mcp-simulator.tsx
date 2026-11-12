"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface Exchange {
  request: { headers: Record<string, string>; body: unknown };
  status: number;
  response: {
    result?: {
      resultType: "complete" | "input_required";
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

function Json({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted-foreground">{label}</p>
      <pre tabIndex={0} className="max-h-72 overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-5">
        {JSON.stringify(value, null, 2)}
      </pre>
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
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Agent hand-off</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Act as an upstream AI agent handing a user&apos;s report to ResolveIT over MCP (protocol 2026-07-28). Each
          call is independent: no session, and any server can answer the retry.
        </p>
      </div>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) void call({}, true);
        }}
      >
        <Label htmlFor="agent-text">The user&apos;s report, verbatim</Label>
        <Textarea id="agent-text" value={text} rows={3} onChange={(e) => setText(e.target.value)} className="bg-card" />
        <Button type="submit" disabled={busy || !text.trim()} className="min-h-11 sm:min-h-9">
          Call submit_incident
        </Button>
        {error ? <p role="alert" className="text-sm text-risk">{error}</p> : null}
      </form>

      <ol className="space-y-4" aria-live="polite">
        {trips.map((trip, i) => (
          <li key={i}>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  Round trip {i + 1}:{" "}
                  {trip.response.error
                    ? `error ${trip.response.error.code}`
                    : trip.response.result?.resultType === "input_required"
                      ? "the server needs one answer"
                      : "complete"}
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <Json label="Request" value={trip.request} />
                <Json label={`Response (HTTP ${trip.status})`} value={trip.response} />
              </CardContent>
            </Card>
          </li>
        ))}
      </ol>

      {pending && ask ? (
        <form
          className="space-y-4 rounded-lg border border-signal/40 bg-accent/40 p-4"
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
                className="h-11 w-full rounded-md border border-input bg-card px-3 text-sm sm:h-9"
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
                className="h-11 w-full rounded-md border border-input bg-card px-3 text-sm sm:h-9"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={busy} className="min-h-11 sm:min-h-9">Retry with answer</Button>
            <Button type="button" variant="outline" disabled={busy} onClick={() => reply({ action: "decline" })} className="min-h-11 sm:min-h-9">
              Decline
            </Button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
