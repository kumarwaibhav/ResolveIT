import lexicon from "@/generated/lexicon.json";

/**
 * Browser-side detail meter. Runs the same rule patterns the server uses
 * (generated from the Python rule engine) with no network call. It shows what
 * the rules can see in the text; it is not a model score.
 */
export type MeterSlot = (typeof lexicon.meter_slots)[number];

const compiled = lexicon.entries.flatMap((entry) => {
  try {
    return [{ slot: entry.slot, re: new RegExp(entry.pattern, "iu") }];
  } catch {
    return []; // a pattern JavaScript cannot compile is skipped; the server still applies it
  }
});
const security = new RegExp(lexicon.security_pattern, "iu");

export const METER_SLOTS: readonly string[] = lexicon.meter_slots;

export const SLOT_LABEL: Record<string, string> = {
  service: "System or app",
  component: "Part affected",
  symptom: "What happens",
  scope: "Who is affected",
  start_time: "When it started",
  frequency: "How often",
  environment: "Where you are",
  error_code: "Error code",
  recent_change: "Recent change",
  user_role_location: "Office or site",
  urgency: "Urgency",
};

export interface MeterResult {
  found: string[];
  missing: string[];
  security: boolean;
}

export function measure(text: string): MeterResult {
  const hit = new Set<string>();
  for (const { slot, re } of compiled) if (!hit.has(slot) && re.test(text)) hit.add(slot);
  return {
    found: METER_SLOTS.filter((s) => hit.has(s)),
    missing: METER_SLOTS.filter((s) => !hit.has(s)),
    security: security.test(text),
  };
}
