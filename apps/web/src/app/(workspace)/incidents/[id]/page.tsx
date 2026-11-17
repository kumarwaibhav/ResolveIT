import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { IncidentPanel } from "@/components/incident/incident-panel";
import { SyntheticBanner } from "@/components/synthetic-banner";
import { apiFetch, isUuid } from "@/lib/server-api";
import type { IncidentView } from "@/lib/types";

export const metadata: Metadata = { title: "Incident" };

export default async function IncidentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!isUuid(id)) notFound();
  const res = await apiFetch(`/v1/incidents/${id}`);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Incident service returned ${res.status}`);
  const view = (await res.json()) as IncidentView;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link href="/" className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground">
        <ArrowLeft aria-hidden="true" className="size-4" /> Report another problem
      </Link>
      <h1 className="text-3xl font-bold tracking-[-0.04em]">Incident record</h1>
      {view.is_synthetic_tenant ? <SyntheticBanner /> : null}
      <IncidentPanel view={view} />
    </div>
  );
}
