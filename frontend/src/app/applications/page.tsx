"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

const COLS = [
  "saved",
  "applied",
  "viewed",
  "interview",
  "offer",
  "rejected",
] as const;

type S = (typeof COLS)[number];

const LABELS: Record<S, string> = {
  saved: "Saved",
  applied: "Applied",
  viewed: "Viewed",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

interface App {
  id: string;
  company: string;
  role: string;
  match_score: number | null;
  status: S;
}

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const { data: apps = [] } = useQuery<App[]>({
    queryKey: ["apps"],
    queryFn: () =>
      apiClient
        .get("/api/v1/jobs/applications")
        .then((r) => r.data as App[]),
  });

  const { mutate } = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiClient.patch(`/api/v1/jobs/applications/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["apps"] }),
    onError: () => toast.error("Update failed"),
  });

  void mutate;

  return (
    <main className="p-8 space-y-4">
      <h1 className="text-2xl font-bold">Applications Pipeline</h1>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {COLS.map((col) => (
          <div key={col} className="min-w-[200px] space-y-2">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">{LABELS[col]}</span>
              <Badge variant="secondary">
                {apps.filter((a) => a.status === col).length}
              </Badge>
            </div>
            {apps
              .filter((a) => a.status === col)
              .map((app) => (
                <Card
                  key={app.id}
                  className="hover:shadow-md transition-shadow"
                >
                  <CardHeader className="pb-1 pt-3 px-3">
                    <CardTitle className="text-sm">{app.company}</CardTitle>
                  </CardHeader>
                  <CardContent className="px-3 pb-3 space-y-1">
                    <p className="text-xs text-slate-500">{app.role}</p>
                    {app.match_score != null && (
                      <Badge variant="outline" className="text-xs">
                        {app.match_score}% match
                      </Badge>
                    )}
                  </CardContent>
                </Card>
              ))}
          </div>
        ))}
      </div>
    </main>
  );
}
