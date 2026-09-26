import type { Metadata } from "next";
import { StatusPageClient } from "@/components/marketing/StatusPageClient";

export const metadata: Metadata = {
  title: "System Status",
  description: "Live status of CareerCraft AI's API, database, cache, and background agent workflows.",
  alternates: { canonical: "/status" },
};

export default function StatusPage() {
  return <StatusPageClient />;
}
