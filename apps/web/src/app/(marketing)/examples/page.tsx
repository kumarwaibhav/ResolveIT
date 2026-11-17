import type { Metadata } from "next";

import { ScenarioGallery, type Observed } from "@/components/landing/scenario-gallery";
import results from "@/generated/scenario-results.json";
import { PageHero } from "@/components/landing/page-hero";

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
  const rows = Object.values(observed);
  const count = (state: string) => rows.filter((r) => r.state === state).length;
  return (
    <>
      <PageHero
        eyebrow="Examples"
        title="Thirty real tickets. Real outcomes."
        sub="Written the way people actually report problems, from Slack, email, WhatsApp and phone calls. Each one was sent to the live demo engine, and this is what came back."
        stats={[
          { label: "Routed to a team", value: count("ROUTED") },
          { label: "Asked one question", value: count("PENDING_CLARIFICATION") },
          { label: "Handed to a person", value: count("DEFERRED") },
          { label: "Languages", value: "English · हिन्दी · Hinglish" },
        ]}
      />
      <div className="mx-auto max-w-6xl px-5 pt-14">
        <ScenarioGallery observed={observed} verifiedAt={verifiedAt} />
      </div>
    </>
  );
}
