import { KeyRound, Lock, ShieldCheck, Timer } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { CodeTabs } from "@/components/docs/code-tabs";
import { Reveal } from "@/components/motion";
import { enumValues, operations, type Field, type Operation } from "@/lib/api-docs";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "API reference" };

const BASE = "https://<your-api-host>";

/** Plain-language layer over the generated contract: purpose, who may call it, and an example. */
const META: Record<string, { group: string; title: string; plain: string; roles: string; example?: string }> = {
  "POST /v1/incidents": { group: "Incidents", title: "Report a problem", plain: "Saves the report first, then returns what was understood and the decision: route, one question, or a person.", roles: "admin · reviewer · agent", example: `{\n  "text": "VPN keeps dropping since this morning for the whole floor",\n  "locale": "en",\n  "channel": "web"\n}` },
  "GET /v1/incidents/{incident_id}": { group: "Incidents", title: "Read an incident", plain: "Returns the frame, evidence and decision. Agents receive the decision but never the decrypted text. Another tenant's ID returns 404.", roles: "any role" },
  "POST /v1/incidents/{incident_id}/answer": { group: "Incidents", title: "Answer the question", plain: "Answers the one optional question, or skips it with null. Returns 409 if the question is already closed.", roles: "admin · reviewer", example: `{ "answer": "vpn" }    // or { "answer": null } to skip` },
  "POST /mcp": { group: "Agents", title: "MCP endpoint", plain: "JSON-RPC endpoint for AI agents using the Model Context Protocol. The enterprise profile adds signed request state; an agent's answer counts only if it quotes the user.", roles: "agent · admin", example: `{ "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {} }` },
  "GET /v1/review": { group: "Review", title: "List the review queue", plain: "Tickets waiting for human labels. With blind=true the model's suggestion is hidden.", roles: "admin · reviewer" },
  "POST /v1/review/{incident_id}/labels": { group: "Review", title: "Submit a label", plain: "One person's independent label: the team plus all 11 details.", roles: "admin · reviewer" },
  "POST /v1/review/{incident_id}/adjudication": { group: "Review", title: "Settle a disagreement", plain: "When two labels disagree, an admin records the final one.", roles: "admin" },
  "GET /v1/review/agreement": { group: "Review", title: "Agreement metrics", plain: "How often independent reviewers agree (Cohen's κ, Krippendorff's α). Null until there are pairs.", roles: "admin · reviewer" },
  "GET /v1/review/export": { group: "Review", title: "Export labels", plain: "Labels eligible for training or testing, with provenance. Synthetic labels are never marked as human gold.", roles: "admin" },
  "POST /v1/review/enqueue": { group: "Review", title: "Backfill the queue", plain: "Adds older incidents to the review queue.", roles: "admin · reviewer" },
  "GET /v1/settings": { group: "Workspace", title: "Read settings", plain: "Queue mapping, cost of a wrong route, cost of a human triage, and timezone.", roles: "admin" },
  "PUT /v1/settings": { group: "Workspace", title: "Update settings", plain: "Send the version you read. A stale version returns 409, so two admins never overwrite each other.", roles: "admin" },
  "GET /v1/evaluation": { group: "Workspace", title: "Certification status", plain: "Which bundle is serving, where its data came from, and whether automatic routing is allowed.", roles: "admin · reviewer · viewer" },
  "POST /v1/bounce/analyze": { group: "Workspace", title: "Analyse handoffs", plain: "Upload an assignment-history CSV (ticket, queue, timestamp). Processed in memory; nothing is stored.", roles: "admin · reviewer" },
  "GET /v1/me": { group: "Workspace", title: "Who am I", plain: "Your tenant, role and whether the tenant is the synthetic demo.", roles: "any role" },
  "POST /v1/privacy/erasure": { group: "Privacy", title: "Erase a person's incidents", plain: "Erases every live incident linked to an exact identifier (email, phone, Aadhaar, PAN…). Backups follow a separate process.", roles: "admin" },
  "GET /healthz": { group: "System", title: "Health check", plain: "Public. Confirms the engine is up and which bundle it serves.", roles: "public" },
};

const GROUPS = ["Incidents", "Agents", "Review", "Workspace", "Privacy", "System"];
const slug = (op: Operation) => `${op.method}-${op.path}`.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-$/, "");
const METHOD = { GET: "bg-info-surface text-info", POST: "bg-ok-surface text-ok", PUT: "bg-warn-surface text-warn", DELETE: "bg-risk-surface text-risk" } as Record<string, string>;

const STATUS = [
  ["200 / 201", "Success."],
  ["400 / 422", "The request body is invalid. The response says which field."],
  ["401", "Missing or rejected key."],
  ["403", "Your role cannot do this."],
  ["404", "Not found, or it belongs to another tenant."],
  ["409", "Conflict: the question is closed, or settings changed since you read them."],
  ["413", "The request body is too large."],
  ["429", "Too many requests in flight. Retry with backoff."],
];

function FieldTable({ title, rows }: { title: string; rows: Field[] }) {
  if (rows.length === 0) return null;
  return (
    <div>
      <p className="mono-label mb-2">{title}</p>
      <div tabIndex={0} className="data-table-wrap rounded-xl border">
        <table className="data-table">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Type</th>
              <th scope="col">Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.name}>
                <th scope="row" className="whitespace-nowrap !font-mono !text-xs">
                  {f.name}
                  {f.required ? <span className="ml-1 text-signal">*</span> : null}
                </th>
                <td className="font-mono text-xs text-muted-foreground">{f.type}</td>
                <td className="text-xs text-muted-foreground">{f.note || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ApiPage() {
  const ops = operations();
  const byGroup = GROUPS.map((g) => ({ g, ops: ops.filter((o) => (META[`${o.method} ${o.path}`]?.group ?? "System") === g) }));
  return (
    <div className="mx-auto max-w-6xl px-5 pt-12">
      <Reveal className="max-w-3xl">
        <p className="eyebrow">Developers · API reference</p>
        <h1 className="text-gradient text-[clamp(2.4rem,5.5vw,4rem)] font-bold leading-[1.02] tracking-[-0.05em]">The ResolveIT API.</h1>
        <p className="mt-5 max-w-xl text-lg text-muted-foreground">
          {ops.length} endpoints, one bearer key per person. Everything this app does, your systems and agents can do too.
        </p>
      </Reveal>

      <div className="mt-12 grid gap-10 lg:grid-cols-[220px_1fr]">
        <nav aria-label="Endpoints" className="top-24 hidden self-start lg:sticky lg:block">
          {byGroup.map(({ g, ops: list }) => (
            <div key={g} className="mb-5">
              <p className="mono-label mb-2">{g}</p>
              <ul className="space-y-1">
                {list.map((o) => (
                  <li key={slug(o)}>
                    <a href={`#${slug(o)}`} className="flex items-center gap-2 rounded-lg py-1 text-sm text-muted-foreground hover:text-foreground">
                      <span className={cn("w-11 shrink-0 rounded px-1 text-center font-mono text-xs font-bold", METHOD[o.method])}>{o.method}</span>
                      <span className="truncate">{META[`${o.method} ${o.path}`]?.title ?? o.summary}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="min-w-0 space-y-14">
          <section aria-labelledby="start" className="space-y-6">
            <h2 id="start" className="text-2xl font-bold tracking-[-0.03em]">Quick start</h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {[
                { Icon: KeyRound, t: "Authenticate", d: "Send Authorization: Bearer <key>. Keys are issued per person by an admin." },
                { Icon: ShieldCheck, t: "Roles", d: "admin, reviewer, viewer and agent. Each endpoint lists who may call it." },
                { Icon: Lock, t: "Tenant isolation", d: "Your key only ever sees your tenant. Other IDs return 404." },
                { Icon: Timer, t: "Cold starts", d: "On the free tier the first call after idle can take up to 30 s." },
              ].map(({ Icon, t, d }) => (
                <li key={t} className="glass flex items-start gap-3 rounded-2xl p-4">
                  <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-signal" />
                  <span>
                    <span className="block text-sm font-bold">{t}</span>
                    <span className="block text-sm text-muted-foreground">{d}</span>
                  </span>
                </li>
              ))}
            </ul>
            <CodeTabs
              samples={[
                { label: "curl", code: `curl -X POST ${BASE}/v1/incidents \\\n  -H "Authorization: Bearer $RESOLVEIT_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"text":"VPN keeps dropping since this morning","locale":"en"}'` },
                { label: "Python", code: `import httpx\n\nr = httpx.post(\n    "${BASE}/v1/incidents",\n    headers={"Authorization": f"Bearer {KEY}"},\n    json={"text": "VPN keeps dropping since this morning", "locale": "en"},\n    timeout=60,\n)\nincident = r.json()\nprint(incident["state"], incident["routed_team"])` },
                { label: "TypeScript", code: `const res = await fetch("${BASE}/v1/incidents", {\n  method: "POST",\n  headers: {\n    Authorization: \`Bearer \${process.env.RESOLVEIT_KEY}\`,\n    "Content-Type": "application/json",\n  },\n  body: JSON.stringify({ text: "VPN keeps dropping since this morning", locale: "en" }),\n});\nconst incident = await res.json();` },
              ]}
            />
          </section>

          <section aria-labelledby="enums" className="space-y-4">
            <h2 id="enums" className="text-2xl font-bold tracking-[-0.03em]">Values you will see</h2>
            <div className="grid gap-3 md:grid-cols-2">
              {[
                ["Incident state", "State"],
                ["Decision", "Action"],
                ["Why it went to a person", "DeferReason"],
                ["Detail status", "EpistemicState"],
              ].map(([label, name]) => {
                const values = name === "State" ? ["PENDING_CLARIFICATION", "ROUTED", "DEFERRED", "BOUNCED", "RESOLVED", "ERASED"] : enumValues(name!);
                return (
                  <div key={name} className="glass rounded-2xl p-4">
                    <p className="text-sm font-bold">{label}</p>
                    <p className="mt-2 flex flex-wrap gap-1.5">
                      {values.map((v) => (
                        <code key={v} className="rounded-md bg-muted px-2 py-0.5 font-mono text-[11px]">{v}</code>
                      ))}
                    </p>
                  </div>
                );
              })}
            </div>
          </section>

          {byGroup.map(({ g, ops: list }) => (
            <section key={g} aria-labelledby={`g-${g}`} className="space-y-5">
              <h2 id={`g-${g}`} className="text-2xl font-bold tracking-[-0.03em]">{g}</h2>
              {list.map((o) => {
                const m = META[`${o.method} ${o.path}`];
                return (
                  <article key={slug(o)} id={slug(o)} className="glass scroll-mt-24 space-y-5 rounded-3xl p-5 sm:p-6">
                    <header>
                      <p className="flex flex-wrap items-center gap-2">
                        <span className={cn("rounded-md px-2 py-0.5 font-mono text-xs font-bold", METHOD[o.method])}>{o.method}</span>
                        <code className="break-all font-mono text-sm font-semibold">{o.path}</code>
                      </p>
                      <h3 className="mt-3 text-lg font-bold tracking-[-0.02em]">{m?.title ?? o.summary}</h3>
                      {m ? <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{m.plain}</p> : null}
                      <p className="mt-3 text-xs">
                        <span className="mono-label">Who</span> <span className="ml-1 font-medium">{m?.roles ?? "authenticated"}</span>
                      </p>
                    </header>
                    {o.params.length > 0 ? (
                      <FieldTable title="Parameters" rows={o.params.map((p) => ({ name: p.name, type: p.type, required: p.required, note: `in ${p.in}` }))} />
                    ) : null}
                    <FieldTable title={`Request body${o.bodyName ? ` · ${o.bodyName}` : ""}`} rows={o.body} />
                    {m?.example ? (
                      <div>
                        <p className="mono-label mb-2">Example</p>
                        <pre tabIndex={0} className="overflow-x-auto rounded-xl bg-[#0c0c0e] p-4 font-mono text-[12.5px] leading-6 text-[#e7e5e4]">{m.example}</pre>
                      </div>
                    ) : null}
                    <FieldTable title={`Response${o.responseName ? ` · ${o.responseName}` : ""}`} rows={o.response} />
                    <p className="flex flex-wrap gap-1.5 text-xs">
                      {o.codes.map((c) => (
                        <code key={c} className={cn("rounded-md px-2 py-0.5 font-mono", c.startsWith("2") ? "bg-ok-surface text-ok" : "bg-muted text-muted-foreground")}>{c}</code>
                      ))}
                    </p>
                  </article>
                );
              })}
            </section>
          ))}

          <section aria-labelledby="errors" className="space-y-4">
            <h2 id="errors" className="text-2xl font-bold tracking-[-0.03em]">Status codes</h2>
            <div tabIndex={0} className="data-table-wrap glass rounded-2xl">
              <table className="data-table">
                <caption className="sr-only">HTTP status codes</caption>
                <thead>
                  <tr>
                    <th scope="col">Code</th>
                    <th scope="col">Meaning</th>
                  </tr>
                </thead>
                <tbody>
                  {STATUS.map(([c, d]) => (
                    <tr key={c}>
                      <th scope="row" className="whitespace-nowrap !font-mono">{c}</th>
                      <td>{d}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-sm text-muted-foreground">
              Building an AI agent? See the <Link href="/mcp" className="font-semibold text-signal underline underline-offset-4">live MCP inspector</Link>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
