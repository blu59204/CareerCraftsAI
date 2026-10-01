"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, getApiErrorMessage } from "@/lib/api";
const sources = ["greenhouse", "lever", "ashby", "workable", "smartrecruiters", "recruitee", "adzuna", "remotive", "remoteok", "arbeitnow", "jsonld"];
type Props = { value: string; onChange: (v: string) => void; source: string; onSource: (v: string) => void; days: number; onDays: (v: number) => void };
export function JobSearchBasis(p: Props) {
  const client = useQueryClient();
  const save = useMutation({ mutationFn: async () => { const [kind, id] = p.value.split(":"); await apiClient.patch("/jobs/search-basis", { basis: { kind, id } }); }, onSuccess: () => client.invalidateQueries({ queryKey: ["job-search-bases"] }) });
  const bases = useQuery<{ options: { kind: string; id: string; label: string; available: boolean }[] }>({ queryKey: ["job-search-bases"], queryFn: async () => (await apiClient.get("/jobs/search/bases")).data });
  const cls = "rounded-lg border border-border bg-background p-2";
  return <div className="flex flex-wrap items-end gap-3 text-sm">
    <label className="grid gap-1">Search basis<select className={cls} value={p.value} onChange={e => p.onChange(e.target.value)} disabled={bases.isPending}>
      <option value="">{bases.isPending ? "Loading…" : "Saved default (or latest resume)"}</option>
      {bases.data?.options.map(o => <option key={`${o.kind}:${o.id}`} value={`${o.kind}:${o.id}`} disabled={!o.available}>{o.label} ({o.kind}){!o.available ? " — unavailable" : ""}</option>)}
    </select></label>
    <button type="button" className={cls} disabled={!p.value || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save default"}</button>
    <label className="grid gap-1">Source<select className={cls} value={p.source} onChange={e => p.onSource(e.target.value)}><option value="">All public sources</option>{sources.map(s => <option key={s}>{s}</option>)}</select></label>
    <label className="grid gap-1">Posted within<select className={cls} value={p.days} onChange={e => p.onDays(Number(e.target.value))}>{[1,7,14,30,90].map(d => <option key={d} value={d}>{d} days</option>)}</select></label>
    {(bases.isError || save.isError) && <p role="alert">{getApiErrorMessage(bases.error || save.error, "Search basis unavailable")}</p>}
    {save.isSuccess && <p role="status">Default saved.</p>}
    {bases.data?.options.length === 0 && <p>Upload a resume to match skills. Role search remains available.</p>}
  </div>;
}
