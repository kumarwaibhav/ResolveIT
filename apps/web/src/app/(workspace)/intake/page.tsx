import type { Metadata } from "next";

import { IntakeWorkspace } from "@/components/intake-workspace";

export const metadata: Metadata = { title: "Report a problem" };

export default function IntakePage() {
  return <IntakeWorkspace />;
}
