import type { ReactNode } from "react";

export function WorkspaceHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: ReactNode }) {
  return <div className="workspace-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="workspace-description">{description}</p></div>{children}</div>;
}

export function LocalDraftNotice() {
  return <p className="local-notice"><span aria-hidden="true">◈</span> Browser-local workspace. Changes are drafts until exported; they are not saved to the server.</p>;
}
