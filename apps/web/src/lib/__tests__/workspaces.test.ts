import { describe, expect, it } from "vitest";
import { agreement, analyzeBounces, evaluatePredictions, parseCsv, TEAMS } from "../workspaces";

describe("workspace analysis", () => {
  it("distinguishes undefined agreement from perfect multiclass agreement", () => {
    expect(agreement([]).kappa).toBeNull();
    expect(agreement([["A", "A"]]).alpha).toBeNull();
    expect(agreement([["A", "A"], ["B", "B"]])).toMatchObject({ n: 2, observed: 1, kappa: 1, alpha: 1 });
    expect(agreement([["A", "B"], ["B", "A"]]).kappa).toBe(-1);
  });
  it("parses escaped multiline fields and rejects malformed quotes", () => {
    expect(parseCsv('id,note\r\n1,"a, b\n""quoted"""')).toEqual([["id", "note"], ["1", 'a, b\n"quoted"']]);
    expect(() => parseCsv('x\n"unclosed')).toThrow("Unclosed");
    expect(() => parseCsv('x\n"closed"tail')).toThrow("Unexpected text");
  });
  it("sorts events, removes identical duplicates and counts queue changes only", () => {
    const result = analyzeBounces("ticket_id,queue,timestamp\n1,B,2026-01-01T02:00:00Z\n1,A,2026-01-01T00:00:00Z\n1,A,2026-01-01T01:00:00Z\n1,B,2026-01-01T02:00:00Z\n2,C,2026-01-01T00:00:00Z");
    expect(result).toMatchObject({ events: 4, changes: 1, bounced: 1 });
    expect(result.tickets[0]).toEqual({ id: "1", queues: ["A", "B"], changes: 1, elapsedHours: 2 });
    expect(() => analyzeBounces("ticket_id,queue,timestamp\n1,A,2026-01-01")).toThrow("timezone");
  });
  it("computes Brier/NLL from supplied probabilities and rejects invalid rows", () => {
    const probs = Object.fromEntries(TEAMS.map((team) => [team, team === "Network" ? 1 : 0]));
    expect(evaluatePredictions([{ label: "Network", probs }])).toEqual({ n: 1, accuracy: 1, brier: 0, nll: 0 });
    expect(() => evaluatePredictions([{ label: "Network", probs: { Network: 1 } }])).toThrow("12 finite");
  });
});
