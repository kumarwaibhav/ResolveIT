import type { Metadata } from "next";

import { ScenarioGallery, type Observed } from "@/components/landing/scenario-gallery";
import results from "@/generated/scenario-results.json";
import { Reveal } from "@/components/motion";

export const metadata: Metadata = { title: "Examples" };

/** Only the fields the cards display travel to the browser. */
function trimmed(): { observed: Record<string, Observed>; verifiedAt: string | null } {
  const raw = results as { verified_at: string | null; results: Record<string, Record<string, unknown>> };
  const keep = ["state", "routed_team", "recommended_team", "defer_reason", "question", "security_trigger", "top_team", "top_p", "found", "round_trip_ms"] as const;
  const observed: Record<string, Observed> = {};
  for (const [id, row] of Object.entries(raw.results)) {
    observed[id] = Object.fromEntries(keep.map((k) => [k, row[k] ?? null])) as unknown as Observed;
  }
  return { observed, verifiedAt: raw.verified_at };
}

export default function ExamplesPage() {
  const { observed, verifiedAt } = trimmed();
  return (
    <div className="mx-auto max-w-6xl px-5 pt-12">
      <Reveal className="mx-auto max-w-3xl text-center">
        <p className="eyebrow">Examples</p>
        <h1 className="text-gradient text-[clamp(2.4rem,5.5vw,4rem)] font-bold leading-[1.02] tracking-[-0.05em]">Thirty real tickets. Real outcomes.</h1>
        <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
          Written the way people actually report problems, from Slack, email, WhatsApp and phone calls. Each one was sent to the live demo engine.
        </p>
      </Reveal>
      <div className="mt-12">
        <ScenarioGallery observed={observed} verifiedAt={verifiedAt} />
      </div>
    </div>
  );
}
