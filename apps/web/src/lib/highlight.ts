import type { SlotView } from "@/lib/types";

export interface Segment {
  text: string;
  slots: string[]; // slots whose evidence covers this segment; empty = plain text
}

/**
 * Cut the text at every evidence boundary. Offsets from the API are UTF-16 code
 * units, which is what String.prototype.slice uses, so emoji and Devanagari
 * never shift a highlight.
 */
export function segments(text: string, frame: SlotView[]): Segment[] {
  const spans = frame.flatMap((s) =>
    (s.evidence ?? [])
      .filter((e) => e.start >= 0 && e.end <= text.length && e.start < e.end)
      .map((e) => ({ start: e.start, end: e.end, slot: s.slot as string })),
  );
  const cuts = [...new Set([0, text.length, ...spans.flatMap((s) => [s.start, s.end])])].sort((a, b) => a - b);
  const out: Segment[] = [];
  for (let i = 0; i < cuts.length - 1; i++) {
    const start = cuts[i]!;
    const end = cuts[i + 1]!;
    if (start === end) continue;
    const slots = [...new Set(spans.filter((s) => s.start <= start && s.end >= end).map((s) => s.slot))];
    out.push({ text: text.slice(start, end), slots });
  }
  return out;
}
