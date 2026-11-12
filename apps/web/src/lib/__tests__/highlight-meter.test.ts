import { describe, expect, it } from "vitest";

import { segments } from "@/lib/highlight";
import { measure } from "@/lib/meter";
import type { SlotView } from "@/lib/types";

const slot = (name: string, start: number, end: number): SlotView =>
  ({ slot: name, state: "PRESENT", value: "x", evidence: [{ start, end, source: "rule" }] }) as SlotView;

describe("segments", () => {
  it("slices by UTF-16 offsets so an emoji does not shift the highlight", () => {
    const text = "😀 VPN is down";
    const out = segments(text, [slot("service", 3, 6)]);
    expect(out.map((s) => s.text)).toEqual(["😀 ", "VPN", " is down"]);
    expect(out[1]?.slots).toEqual(["service"]);
  });

  it("keeps Devanagari clusters intact and rebuilds the full text", () => {
    const text = "वीपीएन फिर से बंद है";
    const out = segments(text, [slot("service", 0, 6), slot("frequency", 7, 13)]);
    expect(out.map((s) => s.text).join("")).toBe(text);
    expect(out[0]).toEqual({ text: "वीपीएन", slots: ["service"] });
  });

  it("handles overlapping evidence and ignores spans outside the text", () => {
    const out = segments("abcdef", [slot("a", 0, 4), slot("b", 2, 6), slot("c", 4, 99)]);
    expect(out).toEqual([
      { text: "ab", slots: ["a"] },
      { text: "cd", slots: ["a", "b"] },
      { text: "ef", slots: ["b"] },
    ]);
  });
});

describe("measure", () => {
  it("finds the same details the server rules do, in English and Hinglish", () => {
    const en = measure("VPN is down again for the whole floor since morning, error 0x80070005, urgent");
    expect(en.found).toEqual(["service", "error_code", "scope", "frequency", "urgency", "start_time"]);
    expect(en.missing).toEqual([]);
    const hi = measure("mera laptop phir se slow hai, jaldi dekho");
    expect(hi.found).toEqual(["service", "frequency", "urgency"]);
  });

  it("reports nothing for an empty message and flags security wording", () => {
    expect(measure("").found).toEqual([]);
    expect(measure("I clicked on a link in a suspicious email").security).toBe(true);
    expect(measure("printer is jammed").security).toBe(false);
  });
});
