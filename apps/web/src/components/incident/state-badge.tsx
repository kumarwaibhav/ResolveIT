import { AlertTriangle, Check, CircleDashed, HelpCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import type { EpistemicState } from "@/lib/types";

export const STATE_STYLE: Record<EpistemicState, { label: string; className: string; Icon: typeof Check }> = {
  PRESENT: { label: "Found", className: "bg-ok-surface text-ok border-ok/25", Icon: Check },
  AMBIGUOUS: { label: "Unclear", className: "bg-warn-surface text-warn border-warn/25", Icon: HelpCircle },
  CONTRADICTED: { label: "Conflicting", className: "bg-risk-surface text-risk border-risk/25", Icon: AlertTriangle },
  MISSING: { label: "Not stated", className: "bg-muted text-muted-foreground border-transparent", Icon: CircleDashed },
};

/** State is carried by the word and the icon; colour only reinforces it. */
export function StateBadge({ state }: { state: EpistemicState }) {
  const { label, className, Icon } = STATE_STYLE[state];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold", className)}>
      <Icon aria-hidden="true" className="size-3.5" />
      {label}
    </span>
  );
}
