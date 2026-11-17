import { StateBadge, STATE_STYLE } from "@/components/incident/state-badge";
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

/** All eleven details at a glance: each tile carries its state as a word and an icon. */
export function SlotGrid({ frame, activeSlot, onActivate }: { frame: SlotView[]; activeSlot: string | null; onActivate: (slot: string | null) => void }) {
  return (
    <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {frame.map((slot) => {
        const s = STATE_STYLE[slot.state];
        return (
          <li
            key={slot.slot}
            onMouseEnter={() => onActivate(slot.slot)}
            onMouseLeave={() => onActivate(null)}
            className={cn(
              "flex items-center gap-2 rounded-xl border px-3 py-2 text-xs transition-colors",
              slot.state === "MISSING" ? "border-dashed bg-transparent text-muted-foreground" : "bg-card",
              activeSlot === slot.slot && "border-signal",
            )}
          >
            <span className={cn("grid size-5 shrink-0 place-items-center rounded-full", s.className)} aria-hidden="true">
              <s.Icon className="size-3" />
            </span>
            <span className="min-w-0 truncate font-medium">{SLOT_LABEL[slot.slot] ?? slot.slot}</span>
            <span className="sr-only">: {s.label}</span>
          </li>
        );
      })}
    </ul>
  );
}

/** Rows only for details the message actually gave; everything not stated is one quiet line. */
export function FrameTable({ frame, decision, activeSlot, onActivate }: Props) {
  const effect = new Map((decision?.attributions ?? []).map((a) => [a.slot as string, a.delta_p]));
  const stated = frame.filter((s) => s.state !== "MISSING");
  const missing = frame.filter((s) => s.state === "MISSING");
  return (
    <div className="space-y-3">
      {stated.length > 0 ? (
        <div tabIndex={0} className="data-table-wrap">
          <table className="data-table">
            <caption className="sr-only">Details found in the message</caption>
            <thead>
              <tr>
                <th scope="col">Detail</th>
                <th scope="col">Understood as</th>
                <th scope="col">Status</th>
                <th scope="col" className="text-right">Team confidence without it</th>
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
                    className={cn(activeSlot === slot.slot && "bg-accent")}
                  >
                    <th scope="row" className="text-left font-semibold">{SLOT_LABEL[slot.slot] ?? slot.slot}</th>
                    <td>{slot.value ? readable(slot.value) : "—"}</td>
                    <td><StateBadge state={slot.state} /></td>
                    <td className="text-right font-mono text-[0.8125rem] tabular">
                      {delta === undefined || Math.abs(delta) < 0.005 ? <span className="font-sans text-muted-foreground">no change</span> : points(delta)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No details could be read from the message.</p>
      )}
      {missing.length > 0 ? (
        <p className="text-sm text-muted-foreground">
          <span className="font-semibold text-foreground">Not stated:</span> {missing.map((s) => SLOT_LABEL[s.slot] ?? s.slot).join(", ")}.
        </p>
      ) : null}
    </div>
  );
}
