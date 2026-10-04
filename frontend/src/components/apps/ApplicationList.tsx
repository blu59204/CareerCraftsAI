"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Trash } from "@phosphor-icons/react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Bezel, IconButton, IslandButton, Select, StatusPill, type StatusTone } from "@/components/vanguard";
import { setApplyState, type AppStage, type ApplicationSort, type ApplyState } from "@/lib/applications-api";
import { startAssistedApply } from "@/lib/assisted-apply";

export type { AppStage };

export type ApplicationItem = {
  id: string;
  company: string;
  role: string;
  matchPercent: number | null;
  stage: AppStage;
  nextFollowUp?: string;
  location?: string | null;
  jobUrl?: string | null;
  jobDescription?: string | null;
  appliedAt?: string | null;
  foundAt?: string | null;
  /** When the employer posted the job (from the source), if known. */
  postedAt?: string | null;
  notes?: string | null;
  source?: string | null;
  resumeLabel?: string | null;
  outreachStatus?: string | null;
  outreachTo?: string | null;
  applyState?: ApplyState | null;
};

export const APP_STAGES: AppStage[] = ["saved", "applied", "viewed", "interview", "offer", "rejected"];

export const STAGE_LABELS: Record<AppStage, string> = {
  saved: "Saved",
  applied: "Applied",
  viewed: "Viewed",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

/** Semantic tone of each stage (status pills). */
export const STAGE_TONE: Record<AppStage, StatusTone> = {
  saved: "neutral",
  applied: "primary",
  viewed: "neutral",
  interview: "warning",
  offer: "success",
  rejected: "danger",
};

const APPLY_LABEL: Record<ApplyState, string> = { opened: "Opened", applied: "Applied", failed: "Failed" };
const APPLY_TONE: Record<ApplyState, StatusTone> = { opened: "primary", applied: "success", failed: "danger" };

/** Assisted apply in the member's own browser: open the job, then the member confirms the outcome. */
export function ApplyControls({ id, jobUrl, state }: { id: string; jobUrl?: string | null; state?: ApplyState | null }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: ["applications"] });
  const start = () => {
    // startAssistedApply opens its tab synchronously, so call it straight from the click.
    setBusy(true);
    void startAssistedApply({ id, job_url: jobUrl ?? null }).finally(() => {
      setBusy(false);
      void refresh();
    });
  };
  const finish = (next: ApplyState) =>
    setApplyState(id, next).then(refresh).catch(() => toast.error("Could not save the result. Try again."));
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {state ? <StatusPill tone={APPLY_TONE[state]}>{APPLY_LABEL[state]}</StatusPill> : null}
      {state === "opened" ? (
        <>
          <IslandButton tone="ghost" size="sm" onClick={() => finish("applied")}>Applied</IslandButton>
          <IslandButton tone="ghost" size="sm" onClick={() => finish("failed")}>Couldn&apos;t apply</IslandButton>
        </>
      ) : state !== "applied" ? (
        <IslandButton tone="ghost" size="sm" disabled={!jobUrl || busy} aria-busy={busy} title={jobUrl ? undefined : "No job link saved"} onClick={start}>
          {state === "failed" ? "Retry" : "Auto apply"}
        </IslandButton>
      ) : null}
    </div>
  );
}

/** "3h ago" / "2d ago"; falls back to a short date after 30 days. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const mins = Math.max(0, Math.floor((Date.now() - then) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 60 * 24) return `${Math.floor(mins / 60)}h ago`;
  if (mins < 60 * 24 * 30) return `${Math.floor(mins / (60 * 24))}d ago`;
  return new Date(then).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

type Props = {
  items: ApplicationItem[];
  onSelect: (id: string) => void;
  onStageChange?: (id: string, newStage: AppStage) => void;
  checked: Set<string>;
  onCheckedChange: (ids: string[], on: boolean) => void;
  onDelete: (id: string) => void;
  sort: ApplicationSort;
  onSortChange: (sort: ApplicationSort) => void;
};

/** Compact table on desktop, labeled cards on phones. */
export function ApplicationList({ items, onSelect, onStageChange, checked, onCheckedChange, onDelete, sort, onSortChange }: Props) {
  const allChecked = items.length > 0 && items.every((item) => checked.has(item.id));
  const foundDir = sort === "found_asc" ? "ascending" : sort === "found_desc" ? "descending" : "none";
  return (
    <Bezel size="md" coreClassName="overflow-hidden">
      <table role="table" className="application-table w-full table-fixed text-left text-sm">
        <caption className="sr-only">Applications and their next steps</caption>
        <thead className="bg-muted/40 text-[11px] uppercase tracking-wider text-muted-foreground">
          <tr>
            <th scope="col" className="w-[28%] px-4 py-3 font-medium">
              <label className="flex items-center gap-3">
                <input type="checkbox" aria-label="Select all applications on this page" checked={allChecked} onChange={(event) => onCheckedChange(items.map((item) => item.id), event.target.checked)} className="h-4 w-4 accent-primary" />
                Role / company
              </label>
            </th>
            <th scope="col" className="w-[14%] px-4 py-3 font-medium">Stage</th>
            <th scope="col" className="w-[8%] px-4 py-3 font-medium">Match</th>
            <th scope="col" className="w-[10%] px-4 py-3 font-medium">Posted</th>
            <th scope="col" aria-sort={foundDir} className="w-[10%] px-4 py-3 font-medium">
              <button type="button" onClick={() => onSortChange(sort === "found_desc" ? "found_asc" : "found_desc")} className="inline-flex items-center gap-1 rounded uppercase tracking-wider hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                Found
                {sort === "found_desc" ? <ArrowDown size={11} weight="bold" aria-hidden /> : sort === "found_asc" ? <ArrowUp size={11} weight="bold" aria-hidden /> : null}
              </button>
            </th>
            <th scope="col" className="w-[10%] px-4 py-3 font-medium">Follow-up</th>
            <th scope="col" className="w-[20%] px-4 py-3 font-medium">Apply</th>
          </tr>
        </thead>
        <tbody role="rowgroup" className="divide-y divide-border">
          {items.map((item) => (
            <tr role="row" key={item.id} className={cn("transition-colors hover:bg-muted/30", checked.has(item.id) && "bg-primary/[0.04]")}>
              <td role="cell" className="px-4 py-3 align-middle">
                <div className="flex items-center gap-3">
                  <input type="checkbox" aria-label={`Select ${item.role} at ${item.company}`} checked={checked.has(item.id)} onChange={(event) => onCheckedChange([item.id], event.target.checked)} className="h-4 w-4 shrink-0 accent-primary" />
                  <button type="button" onClick={() => onSelect(item.id)} className="block min-w-0 flex-1 rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                    <span className="block truncate font-medium text-foreground">{item.role}</span>
                    <span className="mt-1 block truncate text-xs text-muted-foreground">{item.company}{item.location ? ` · ${item.location}` : ""}</span>
                  </button>
                  <IconButton size="sm" aria-label={`Delete ${item.role} at ${item.company}`} onClick={() => onDelete(item.id)}><Trash size={13} weight="light" /></IconButton>
                </div>
              </td>
              <td role="cell" data-label="Stage" className="px-4 py-3 align-middle">
                {onStageChange ? (
                  <Select aria-label={`Stage for ${item.role} at ${item.company}`} value={item.stage} onChange={(event) => onStageChange(item.id, event.target.value as AppStage)} className="h-9 px-2 pr-7 text-xs">
                    {APP_STAGES.map((stage) => <option key={stage} value={stage}>{STAGE_LABELS[stage]}</option>)}
                  </Select>
                ) : <StatusPill tone={STAGE_TONE[item.stage]}>{STAGE_LABELS[item.stage]}</StatusPill>}
              </td>
              <td role="cell" data-label="Match" className="px-4 py-3 align-middle font-geist-mono tabular-nums text-primary">{item.matchPercent != null ? `${item.matchPercent}%` : "—"}</td>
              <td role="cell" data-label="Posted" className="px-4 py-3 align-middle text-xs text-muted-foreground">
                <span title={item.postedAt ? new Date(item.postedAt).toLocaleString() : "Posting date not listed by the source"}>{relativeTime(item.postedAt)}</span>
              </td>
              <td role="cell" data-label="Found" className="px-4 py-3 align-middle text-xs text-muted-foreground">
                <span title={item.foundAt ? new Date(item.foundAt).toLocaleString() : undefined}>{relativeTime(item.foundAt)}</span>
              </td>
              <td role="cell" data-label="Follow-up" className="px-4 py-3 align-middle text-xs text-muted-foreground">{item.nextFollowUp ?? "Not scheduled"}</td>
              <td role="cell" data-label="Apply" className="px-4 py-3 align-middle"><ApplyControls id={item.id} jobUrl={item.jobUrl} state={item.applyState} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Bezel>
  );
}
