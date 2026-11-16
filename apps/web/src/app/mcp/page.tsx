import type { Metadata } from "next";

import { McpSimulator } from "@/components/mcp-simulator";
import { ArchitectureExplorer } from "@/components/architecture-explorer";

export const metadata: Metadata = { title: "Agent hand-off" };

export default function McpPage() {
  return <div className="space-y-7"><McpSimulator /><ArchitectureExplorer /></div>;
}
