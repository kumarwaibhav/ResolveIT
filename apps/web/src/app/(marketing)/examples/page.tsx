import type { Metadata } from "next";

import { ScenarioGallery } from "@/components/landing/scenario-gallery";
import { Reveal } from "@/components/motion";

export const metadata: Metadata = { title: "Examples" };

export default function ExamplesPage() {
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
        <ScenarioGallery />
      </div>
    </div>
  );
}
