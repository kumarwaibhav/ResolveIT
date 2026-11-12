import { StateBadge } from "@/components/incident/state-badge";
import { SLOT_LABEL } from "@/lib/meter";
import { cn } from "@/lib/utils";
import type { Decision, SlotView } from "@/lib/types";

interface Props {
  frame: SlotView[];
  decision: Decision | null;
  activeSlot: string | null;
  onActivate: (slot: string | null) => void;
}

const when = new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" });
const readable = (value: string): string =>
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value) ? when.format(new Date(value)) : value.replaceAll("_", " ");
const points = (delta: number): string => `${delta >= 0 ? "−" : "+"}${Math.abs(delta * 100).toFixed(0)} pts`;

/** Rows only for details the message actually gave; everything not stated is one quiet line. */
export function FrameTable({ frame, decision, activeSlot, onActivate }: Props) {
  const effect = new Map((decision?.attributions ?? []).map((a) => [a.slot as string, a.delta_p]));
  const stated = frame.filter((s) => s.state !== "MISSING");
  const missing = frame.filter((s) => s.state === "MISSING");
  return (
    <div className="space-y-3">
      {stated.length > 0 ? (
        <table className="w-full text-sm">
          <caption className="sr-only">Details found in the message</caption>
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th scope="col" className="py-2 pr-3 font-medium">Detail</th>
              <th scope="col" className="py-2 pr-3 font-medium">Understood as</th>
              <th scope="col" className="py-2 pr-3 font-medium">Status</th>
              <th scope="col" className="py-2 text-right font-medium">Team confidence without it</th>
            </tr>
          </thead>
          <tbody>
            {stated.map((slot) => {
              const delta = effect.get(slot.slot);
              return (
                <tr
                  key={slot.slot}
                  onMouseEnter={() => onActivate(slot.slot)}
                  onMouseLeave={() => onActivate(null)}
                  className={cn("border-b last:border-0", activeSlot === slot.slot && "bg-accent")}
                >
                  <th scope="row" className="py-2 pr-3 text-left font-normal">{SLOT_LABEL[slot.slot] ?? slot.slot}</th>
                  <td className="py-2 pr-3">{slot.value ? readable(slot.value) : "—"}</td>
                  <td className="py-2 pr-3"><StateBadge state={slot.state} /></td>
                  <td className="py-2 text-right font-mono text-[0.8125rem] tabular-nums">
                    {delta === undefined || Math.abs(delta) < 0.005 ? (
                      <span className="font-sans text-muted-foreground">no change</span>
                    ) : (
                      points(delta)
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className="text-sm text-muted-foreground">No details could be read from the message.</p>
      )}
      {missing.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Not stated:</span>{" "}
          {missing.map((s) => SLOT_LABEL[s.slot] ?? s.slot).join(", ")}.
        </p>
      ) : null}
    </div>
  );
}
