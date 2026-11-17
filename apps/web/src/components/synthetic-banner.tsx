import { FlaskConical } from "lucide-react";

/** Permanent on demo tenants. Not dismissible by design. */
export function SyntheticBanner() {
  return (
    <p role="note" className="flex items-start gap-3 rounded-2xl border border-warn/30 bg-warn-surface px-4 py-3 text-sm leading-relaxed text-warn">
      <FlaskConical aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>
        <strong className="font-semibold">Synthetic demo data.</strong> Decisions here come from a bundle calibrated on generated tickets. They are
        excluded from evaluation and say nothing about real accuracy.
      </span>
    </p>
  );
}
