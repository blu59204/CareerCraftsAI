"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";

type Status = "operational" | "degraded" | "outage" | "unknown";

const STATUS_STYLES: Record<Status, string> = {
  operational: "bg-success/15 text-success",
  degraded: "bg-warning/15 text-warning",
  outage: "bg-danger/15 text-danger",
  unknown: "bg-muted text-muted-foreground",
};

const STATUS_DOT: Record<Status, string> = {
  operational: "bg-success",
  degraded: "bg-warning",
  outage: "bg-danger",
  unknown: "bg-muted-foreground",
};

const STATUS_LABEL: Record<Status, string> = {
  operational: "operational",
  degraded: "degraded",
  outage: "outage",
  unknown: "not monitored",
};

// Services we cannot probe from the public status page are honestly marked
// "not monitored" rather than reported as operational.
const STATIC_SERVICES: { name: string; status: Status }[] = [
  { name: "Authentication", status: "unknown" },
  { name: "Agent Orchestrator", status: "unknown" },
  { name: "Job Search (browser-use)", status: "unknown" },
  { name: "Email Agent (Gmail MCP)", status: "unknown" },
  { name: "RAG Pipeline", status: "unknown" },
];

export default function StatusPage() {
  const [apiStatus, setApiStatus] = useState<Status>("unknown");
  const [checkedAt, setCheckedAt] = useState<string>("checking…");

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        // /health lives at the API root, not under /api/v1 — strip the suffix.
        const base = (apiClient.defaults.baseURL ?? "").replace(/\/api\/v1\/?$/, "");
        const res = await fetch(`${base}/health`, { cache: "no-store" });
        if (cancelled) return;
        setApiStatus(res.ok ? "operational" : "outage");
      } catch {
        if (!cancelled) setApiStatus("outage");
      } finally {
        if (!cancelled) setCheckedAt(new Date().toLocaleTimeString());
      }
    };
    probe();
    const interval = setInterval(probe, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const services: { name: string; status: Status }[] = [
    { name: "API (FastAPI)", status: apiStatus },
    // Database health is reflected by the API probe (the API depends on it).
    { name: "Database", status: apiStatus },
    ...STATIC_SERVICES,
  ];

  const headline =
    apiStatus === "operational"
      ? "Core systems operational."
      : apiStatus === "outage"
        ? "API is unreachable."
        : "Checking system status…";

  return (
    <div className="mx-auto max-w-2xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">System Status</div>
      <h1 className="text-4xl font-medium">{headline}</h1>
      <p className="mt-3 text-muted-foreground">
        Live health of the CareerCraft AI API. Components marked &ldquo;not monitored&rdquo;
        are not probed from this page.
      </p>

      <div className="mt-8 divide-y divide-border rounded-3xl border border-border bg-card/60">
        {services.map((service) => (
          <div key={service.name} className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <span className={`h-2 w-2 rounded-full ${STATUS_DOT[service.status]}`} />
              <span className="text-sm font-medium">{service.name}</span>
            </div>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[service.status]}`}>
              {STATUS_LABEL[service.status]}
            </span>
          </div>
        ))}
      </div>

      <p className="mt-6 text-xs text-muted-foreground">Last checked: {checkedAt}</p>
    </div>
  );
}
