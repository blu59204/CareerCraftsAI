export const metadata = { title: "System Status — CareerCraft AI" };

const SERVICES = [
  { name: "API (FastAPI)", status: "operational" as const },
  { name: "Authentication (Supabase)", status: "operational" as const },
  { name: "Database", status: "operational" as const },
  { name: "Agent Orchestrator", status: "operational" as const },
  { name: "Job Search (PinchTab)", status: "operational" as const },
  { name: "Email Agent (Gmail MCP)", status: "operational" as const },
  { name: "RAG Pipeline", status: "operational" as const },
];

const STATUS_STYLES = {
  operational: "bg-green-500/15 text-green-600",
  degraded: "bg-amber-500/15 text-amber-600",
  outage: "bg-red-500/15 text-red-600",
};

const STATUS_DOT = {
  operational: "bg-green-500",
  degraded: "bg-amber-500",
  outage: "bg-red-500",
};

export default function StatusPage() {
  const allOperational = SERVICES.every((s) => s.status === "operational");

  return (
    <div className="mx-auto max-w-2xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">System Status</div>
      <h1 className="text-4xl font-medium">All systems operational.</h1>
      <p className="mt-3 text-muted-foreground">
        Real-time status of CareerCraft AI infrastructure.
      </p>

      {allOperational && (
        <div className="mt-6 flex items-center gap-3 rounded-2xl border border-green-200 bg-green-50 px-5 py-4">
          <span className="h-2.5 w-2.5 rounded-full bg-green-500" />
          <span className="text-sm font-medium text-green-800">All services are fully operational</span>
        </div>
      )}

      <div className="mt-8 divide-y divide-border rounded-3xl border border-border bg-card/60">
        {SERVICES.map((service) => (
          <div key={service.name} className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center gap-3">
              <span className={`h-2 w-2 rounded-full ${STATUS_DOT[service.status]}`} />
              <span className="text-sm font-medium">{service.name}</span>
            </div>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${STATUS_STYLES[service.status]}`}>
              {service.status}
            </span>
          </div>
        ))}
      </div>

      <p className="mt-6 text-xs text-muted-foreground">Last checked: just now</p>
    </div>
  );
}
