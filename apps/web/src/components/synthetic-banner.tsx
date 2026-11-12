/** Permanent on demo tenants. Not dismissible by design. */
export function SyntheticBanner() {
  return (
    <p role="note" className="rounded-md border border-warn/40 bg-warn-surface px-3 py-2 text-sm text-warn">
      <strong className="font-semibold">Synthetic demo data.</strong> Decisions here come from a bundle calibrated on
      generated tickets. They are excluded from evaluation and say nothing about real accuracy.
    </p>
  );
}
