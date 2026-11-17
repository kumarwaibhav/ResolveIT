import { segments } from "@/lib/highlight";
import { SLOT_LABEL } from "@/lib/meter";
import { cn } from "@/lib/utils";
import type { SlotView } from "@/lib/types";

interface Props {
  text: string;
  frame: SlotView[];
  activeSlot: string | null;
  onActivate: (slot: string | null) => void;
}

/**
 * The user's own words with the evidence underlined in place. Each marked span
 * names its slot in text, so the link to the frame does not depend on colour.
 */
export function EvidenceText({ text, frame, activeSlot, onActivate }: Props) {
  return (
    <p className="whitespace-pre-wrap break-words text-[17px] leading-9 tracking-[-0.01em]" lang="und">
      {segments(text, frame).map((seg, i) => {
        if (seg.slots.length === 0) return <span key={i}>{seg.text}</span>;
        const active = activeSlot !== null && seg.slots.includes(activeSlot);
        const names = seg.slots.map((s) => SLOT_LABEL[s] ?? s).join(", ");
        return (
          <mark
            key={i}
            onMouseEnter={() => onActivate(seg.slots[0] ?? null)}
            onMouseLeave={() => onActivate(null)}
            className={cn(
              "rounded-md bg-transparent px-0.5 text-foreground underline decoration-signal decoration-2 underline-offset-[6px] transition-colors",
              active && "bg-accent text-accent-foreground",
            )}
          >
            {seg.text}
            <span className="ml-1 inline-block align-super font-mono text-[0.625rem] leading-none font-semibold uppercase tracking-wide text-signal">
              <span className="sr-only"> (evidence for </span>
              {names}
              <span className="sr-only">)</span>
            </span>
          </mark>
        );
      })}
    </p>
  );
}
