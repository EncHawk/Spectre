import { MarketingHome } from "@/components/marketing-home";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Spectre — Find the ghosts in your agents",
  description: "Challenge your agent with GEPA, follow failures through NeatLogs, and let Theo turn trace evidence into a suggested fix and verification plan.",
};

export default function HomePage() {
  return <MarketingHome />;
}
