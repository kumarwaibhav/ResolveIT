export const TEAMS = ["Network", "Identity_Access", "Email_Collab", "Hardware_Endpoint", "Software_Licensing", "Database", "Cloud_Infra", "Security", "ERP_Finance", "HR_Systems", "DevOps_CICD", "Facilities_AV"] as const;

/** Nominal agreement for exactly two independent ratings per item. Null means undefined. */
export function agreement(pairs: readonly (readonly [string, string])[]) {
  const n = pairs.length;
  if (!n) return { n, observed: null, kappa: null, alpha: null };
  const left = new Map<string, number>(), right = new Map<string, number>(), pooled = new Map<string, number>();
  let matches = 0;
  for (const [a, b] of pairs) {
    left.set(a, (left.get(a) ?? 0) + 1); right.set(b, (right.get(b) ?? 0) + 1);
    pooled.set(a, (pooled.get(a) ?? 0) + 1); pooled.set(b, (pooled.get(b) ?? 0) + 1);
    matches += Number(a === b);
  }
  const observed = matches / n;
  let expected = 0;
  for (const [label, count] of left) expected += count * (right.get(label) ?? 0) / (n * n);
  const total = 2 * n;
  const expectedDisagreement = (total * total - [...pooled.values()].reduce((s, count) => s + count * count, 0)) / (total * (total - 1));
  return { n, observed, kappa: expected < 1 ? (observed - expected) / (1 - expected) : null, alpha: expectedDisagreement > 0 ? 1 - (1 - observed) / expectedDisagreement : null };
}

/** RFC-4180-style CSV parser: quotes, escaped quotes, CRLF and embedded newlines. */
export function parseCsv(source: string): string[][] {
  const rows: string[][] = []; let row: string[] = [], cell = "", quoted = false, closed = false;
  const input = source.replace(/^\uFEFF/, "");
  for (let i = 0; i < input.length; i++) {
    const char = input[i]!;
    if (quoted) {
      if (char === '"') { if (input[i + 1] === '"') { cell += '"'; i++; } else { quoted = false; closed = true; } }
      else cell += char;
    } else if (char === '"') {
      if (cell || closed) throw new Error(`Unexpected quote near character ${i + 1}.`);
      quoted = true;
    } else if (char === ",") { row.push(cell); cell = ""; closed = false; }
    else if (char === "\n" || char === "\r") {
      if (char === "\r" && input[i + 1] === "\n") i++;
      row.push(cell); if (row.some((value) => value.trim())) rows.push(row); row = []; cell = ""; closed = false;
    } else {
      if (closed && char.trim()) throw new Error(`Unexpected text after closing quote near character ${i + 1}.`);
      if (!closed) cell += char;
    }
  }
  if (quoted) throw new Error("Unclosed quoted CSV field.");
  row.push(cell); if (row.some((value) => value.trim())) rows.push(row);
  return rows;
}

export type BounceTicket = { id: string; queues: string[]; changes: number; elapsedHours: number };
export function analyzeBounces(source: string): { tickets: BounceTicket[]; events: number; changes: number; bounced: number } {
  const rows = parseCsv(source);
  if (rows.length < 2) throw new Error("Add a header and at least one assignment event.");
  const header = rows[0]!.map((value) => value.trim().toLowerCase());
  const cols = ["ticket_id", "queue", "timestamp"].map((name) => header.indexOf(name));
  if (cols.some((idx) => idx < 0)) throw new Error("Required columns: ticket_id, queue, timestamp.");
  const grouped = new Map<string, { queue: string; time: number; order: number }[]>();
  const seen = new Set<string>();
  rows.slice(1).forEach((row, idx) => {
    if (row.length !== header.length) throw new Error(`Row ${idx + 2}: column count does not match header.`);
    const [id = "", queue = "", stamp = ""] = cols.map((col) => row[col]?.trim() ?? "");
    if (!id || !queue || !stamp || !/(?:Z|[+-]\d\d:\d\d)$/.test(stamp)) throw new Error(`Row ${idx + 2}: ticket, queue and timestamp with timezone are required.`);
    const time = Date.parse(stamp);
    if (!Number.isFinite(time)) throw new Error(`Row ${idx + 2}: timestamp is invalid.`);
    const key = JSON.stringify([id, queue, time]); if (seen.has(key)) return; seen.add(key);
    const events = grouped.get(id) ?? []; events.push({ queue, time, order: idx }); grouped.set(id, events);
  });
  const tickets = [...grouped].map(([id, events]) => {
    events.sort((a, b) => a.time - b.time || a.order - b.order);
    const queues = events.filter((event, idx) => idx === 0 || event.queue !== events[idx - 1]!.queue).map((event) => event.queue);
    return { id, queues, changes: Math.max(queues.length - 1, 0), elapsedHours: (events.at(-1)!.time - events[0]!.time) / 3_600_000 };
  }).sort((a, b) => b.changes - a.changes || a.id.localeCompare(b.id));
  return { tickets, events: seen.size, changes: tickets.reduce((sum, ticket) => sum + ticket.changes, 0), bounced: tickets.filter((ticket) => ticket.changes > 0).length };
}

export type EvalRow = { label: string; probs: Record<string, number> };
export function evaluatePredictions(rows: EvalRow[]) {
  if (!rows.length) throw new Error("At least one prediction is required.");
  let correct = 0, brier = 0, nll = 0;
  for (const row of rows) {
    const values = TEAMS.map((team) => row.probs[team] ?? NaN);
    if (!TEAMS.includes(row.label as typeof TEAMS[number]) || values.some((p) => !Number.isFinite(p) || p < 0 || p > 1) || Math.abs(values.reduce((sum, p) => sum + p, 0) - 1) > 1e-6) throw new Error("Each row needs a canonical label and 12 finite probabilities summing to one.");
    const predicted = TEAMS[values.indexOf(Math.max(...values))];
    correct += Number(predicted === row.label);
    brier += TEAMS.reduce((sum, team, idx) => sum + (values[idx]! - Number(team === row.label)) ** 2, 0);
    nll += -Math.log(Math.max(row.probs[row.label] ?? 0, 1e-15));
  }
  return { n: rows.length, accuracy: correct / rows.length, brier: brier / rows.length, nll: nll / rows.length };
}

export function downloadJson(name: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2) + "\n"], { type: "application/json" }));
  const link = document.createElement("a"); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
}

/** Stable allocation by incident group; assignment does not change when labels do. */
export function draftSplit(group: string) {
  let hash = 2166136261;
  for (const char of group) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0;
  const bucket = hash % 100;
  return bucket < 60 ? "training" : bucket < 75 ? "scaling" : bucket < 90 ? "calibration" : "frozen_test";
}
