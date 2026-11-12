import { Check, Minus } from "lucide-react";

import { SLOT_LABEL, type MeterResult } from "@/lib/meter";

/** Counts what the rule patterns can see in the text. Runs in the browser; nothing is sent while typing. */
export function DetailMeter({ result }: { result: MeterResult }) {
  const total = result.found.length + result.missing.length;
  return (
    <section aria-labelledby="meter-heading" className="space-y-2">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="meter-heading" className="text-sm font-medium">Details spotted so far</h2>
        <p className="font-mono text-sm tabular-nums" aria-live="polite">
          {result.found.length} of {total}
        </p>
      </div>
      <div
        role="meter"
        aria-labelledby="meter-heading"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={result.found.length}
        aria-valuetext={`${result.found.length} of ${total} details`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-secondary"
      >
        <div className="h-full rounded-full bg-signal transition-[width]" style={{ width: `${(result.found.length / total) * 100}%` }} />
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {[...result.found.map((s) => [s, true] as const), ...result.missing.map((s) => [s, false] as const)].map(
          ([slot, found]) => (
            <li key={slot} className={found ? "text-foreground" : "text-muted-foreground"}>
              {found ? (
                <Check aria-hidden="true" className="mr-1 inline size-3.5 text-ok" />
              ) : (
                <Minus aria-hidden="true" className="mr-1 inline size-3.5" />
              )}
              {SLOT_LABEL[slot] ?? slot}
              <span className="sr-only">{found ? ", found" : ", not yet stated"}</span>
            </li>
          ),
        )}
      </ul>
      <p className="text-xs text-muted-foreground">Checked on this device as you type. Missing details never block sending.</p>
    </section>
  );
}
