import type { components } from "@/generated/api";

export type ReviewItem = components["schemas"]["ReviewItem"];
export type ReviewList = components["schemas"]["ReviewList"];
export type HumanLabel = components["schemas"]["HumanLabel"];
export type AgreementResult = components["schemas"]["AgreementResult"];
export type TenantSettings = components["schemas"]["TenantSettings"];
export type EvaluationStatus = components["schemas"]["EvaluationStatus"];
export type BounceReport = components["schemas"]["BounceReport"];

export async function workspaceApi<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api/workspaces/${path}`, { method, cache: "no-store", ...(body === undefined ? {} : { headers: { "content-type": "application/json" }, body: JSON.stringify(body) }) });
  if (!response.ok) {
    let detail = `Workspace service returned ${response.status}.`;
    try { const data: unknown = await response.json(); if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") detail = data.detail; } catch { /* Keep safe status message for non-JSON failures. */ }
    throw new Error(detail);
  }
  return await response.json() as T;
}
