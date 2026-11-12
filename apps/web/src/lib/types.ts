// Aliases over the generated OpenAPI types. Never hand-write an API shape here.
import type { components } from "@/generated/api";

type S = components["schemas"];
export type IncidentView = S["IncidentView"];
export type IncidentCreate = S["IncidentCreate"];
export type SlotView = S["SlotView"];
export type EvidenceView = S["EvidenceView"];
export type QuestionView = S["QuestionView"];
export type Decision = S["Decision"];
export type Slot = S["Slot"];
export type EpistemicState = S["EpistemicState"];
export type Locale = IncidentCreate["locale"];
