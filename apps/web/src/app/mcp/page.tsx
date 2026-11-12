import type { Metadata } from "next";

import { McpSimulator } from "@/components/mcp-simulator";

export const metadata: Metadata = { title: "Agent hand-off" };

export default function McpPage() {
  return <McpSimulator />;
}
