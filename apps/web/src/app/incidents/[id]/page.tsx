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
      <p className="text-sm">
        <Link href="/" className="text-signal underline underline-offset-4">Report another problem</Link>
      </p>
      <h1 className="sr-only">Incident</h1>
      {view.is_synthetic_tenant ? <SyntheticBanner /> : null}
      <IncidentPanel view={view} />
    </div>
  );
}
