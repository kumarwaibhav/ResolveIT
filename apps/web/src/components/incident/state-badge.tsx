import { AlertTriangle, Check, CircleDashed, HelpCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import type { EpistemicState } from "@/lib/types";

const STYLE: Record<EpistemicState, { label: string; className: string; Icon: typeof Check }> = {
  PRESENT: { label: "Found", className: "bg-ok-surface text-ok", Icon: Check },
  AMBIGUOUS: { label: "Unclear", className: "bg-warn-surface text-warn", Icon: HelpCircle },
  CONTRADICTED: { label: "Conflicting", className: "bg-risk-surface text-risk", Icon: AlertTriangle },
  MISSING: { label: "Not stated", className: "bg-muted text-muted-foreground", Icon: CircleDashed },
};

/** State is carried by the word and the icon; colour only reinforces it. */
export function StateBadge({ state }: { state: EpistemicState }) {
  const { label, className, Icon } = STYLE[state];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium", className)}>
      <Icon aria-hidden="true" className="size-3.5" />
      {label}
    </span>
  );
}
