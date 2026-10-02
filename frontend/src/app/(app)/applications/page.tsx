"use client";

import { Suspense, useEffect, useId, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowSquareOut,
  ArrowsLeftRight,
  Briefcase,
  CaretDown,
  CircleNotch,
  Export,
  FileCsv,
  MagnifyingGlass,
  Table,
  Trash,
  Tray,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { ApplicationList, type ApplicationItem, type AppStage } from "@/components/apps/ApplicationList";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { deleteApplications, fetchApplications, restoreApplications, type ApplicationFilters, type ApplicationRecord, type ApplicationSort } from "@/lib/applications-api";
import { ApplicationDrawer } from "@/components/apps/ApplicationDrawer";
import {
  Bezel,
  Chip,
  EmptyPanel,
  IconButton,
  IslandButton,
  IslandLink,
  Input,
  PageHero,
  Reveal,
  SPRING_SOFT,
  Screen,
  Section,
  Skeleton,
  StatStrip,
} from "@/components/vanguard";
import { apiClient } from "@/lib/api";

type AgentRun = {
  id: string;
  agent_type: string;
  status: string;
  started_at: string;
  output_summary?: string;
};

function nextFollowUp(application: ApplicationRecord): string | undefined {
  const next = [application.followup_day5, application.followup_day12]
    .filter((date): date is string => !!date && new Date(date).getTime() > Date.now())
    .sort()[0];
  return next ? new Date(next).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : undefined;
}

const MATCH_CHIPS = [{ label: "Any", value: 0 }, { label: "≥50", value: 50 }, { label: "≥70", value: 70 }, { label: "≥80", value: 80 }];
const FOUND_CHIPS = [{ label: "Any", value: "any" }, { label: "Today", value: "today" }, { label: "7d", value: "7d" }, { label: "30d", value: "30d" }, { label: "Custom", value: "custom" }] as const;
type FoundRange = (typeof FOUND_CHIPS)[number]["value"];
const SORTS: ApplicationSort[] = ["found_desc", "found_asc", "match_desc", "match_asc"];
const DAY_MS = 86_400_000;

export default function ApplicationsPage() {
  // useSearchParams needs a Suspense boundary under the App Router.
  return (
    <Suspense fallback={null}>
      <ApplicationsView />
    </Suspense>
  );
}

function ApplicationsView() {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [search, setSearch] = useState("");
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<string[] | null>(null);
  const [matchDraft, setMatchDraft] = useState<number | null>(null);

  // Filter + sort state lives in the URL so reload/share keeps it.
  const minMatch = Math.min(100, Math.max(0, Number(params.get("min")) || 0));
  const foundParam = params.get("found");
  const found: FoundRange = FOUND_CHIPS.some((c) => c.value === foundParam) ? (foundParam as FoundRange) : "any";
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const sortParam = params.get("sort") as ApplicationSort | null;
  const sort: ApplicationSort = sortParam && SORTS.includes(sortParam) ? sortParam : "found_desc";

  const setParams = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  // Memoised on URL params so relative ranges ("7d") don't change the query key every render.
  const filters = useMemo<ApplicationFilters>(() => {
    const f: ApplicationFilters = { sort };
    if (minMatch > 0) f.minMatch = minMatch;
    const now = Date.now();
    if (found === "today") f.foundAfter = new Date(new Date().setHours(0, 0, 0, 0)).toISOString();
    else if (found === "7d") f.foundAfter = new Date(now - 7 * DAY_MS).toISOString();
    else if (found === "30d") f.foundAfter = new Date(now - 30 * DAY_MS).toISOString();
    else if (found === "custom") {
      if (from) f.foundAfter = new Date(`${from}T00:00:00`).toISOString();
      if (to) f.foundBefore = new Date(`${to}T23:59:59.999`).toISOString();
    }
    return f;
  }, [sort, minMatch, found, from, to]);
  const filtersActive = minMatch > 0 || found !== "any";

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["applications", filters],
    queryFn: async () => {
      const page = await fetchApplications(filters);
      return {
        total: page.total,
        items: page.items.map((application: ApplicationRecord): ApplicationItem => ({
          id: String(application.id),
          company: application.company,
          role: application.role,
          location: application.location,
          jobUrl: application.job_url,
          jobDescription: application.jd_text,
          matchPercent: application.match_score,
          stage: application.status,
          appliedAt: application.applied_at,
          foundAt: application.found_at,
          nextFollowUp: nextFollowUp(application),
          notes: application.notes,
          source: application.source,
          resumeLabel: application.resume_label,
          outreachStatus: application.outreach_status,
          outreachTo: application.outreach_to,
        })),
      };
    },
    placeholderData: (previous) => previous,
  });
  const items = useMemo(() => data?.items ?? [], [data]);
  const total = data?.total ?? 0;

  const { data: activityRuns = [] } = useQuery<AgentRun[]>({
    queryKey: ["agent-runs", selectedId],
    enabled: !!selectedId,
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs", { params: { application_id: selectedId, limit: 10 } });
      return (Array.isArray(data) ? data : data.runs ?? []) as AgentRun[];
    },
  });

  const statusMutation = useMutation({
    mutationFn: async ({ id, newStage }: { id: string; newStage: AppStage }) => {
      await apiClient.patch(`/jobs/applications/${id}/status`, { status: newStage });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      toast.success("Status updated");
    },
    onError: () => toast.error("Could not update the application status"),
  });

  const deleteMutation = useMutation({
    mutationFn: (ids: string[]) => deleteApplications(ids),
    onSuccess: (_res, ids) => {
      setPendingDelete(null);
      setChecked(new Set());
      if (selectedId && ids.includes(selectedId)) setSelectedId(null);
      qc.invalidateQueries({ queryKey: ["applications"] });
      toast.success(ids.length === 1 ? "Application deleted" : `${ids.length} applications deleted`, {
        duration: 8000,
        action: {
          label: "Undo",
          onClick: () =>
            restoreApplications(ids)
              .then(() => toast.success("Restored"))
              .catch(() => toast.error("Could not restore"))
              .finally(() => qc.invalidateQueries({ queryKey: ["applications"] })),
        },
      });
    },
    onError: () => toast.error("Could not delete. Nothing was changed."),
  });

  const selected = items.find((item) => item.id === selectedId) ?? null;
  const filteredItems = items.filter((item) =>
    `${item.company} ${item.role} ${item.location ?? ""}`.toLowerCase().includes(search.trim().toLowerCase())
  );
  const checkedIds = filteredItems.filter((item) => checked.has(item.id)).map((item) => item.id);
  const activeCount = items.filter((item) => ["applied", "viewed", "interview"].includes(item.stage)).length;
  const interviewCount = items.filter((item) => item.stage === "interview").length;
  const offerCount = items.filter((item) => item.stage === "offer").length;

  const onCheckedChange = (ids: string[], on: boolean) =>
    setChecked((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (on) next.add(id);
        else next.delete(id);
      }
      return next;
    });

  const exportToCSV = () => {
    const csvCell = (value: string | number | null | undefined) =>
      `"${String(value ?? "").replace(/"/g, '""')}"`;
    const headers = ["Company", "Role", "Location", "Source", "Match %", "Stage", "Found", "Next follow-up"];
    const rows = items.map((item) => [
      item.company, item.role, item.location, item.jobUrl, item.matchPercent, item.stage, item.foundAt, item.nextFollowUp,
    ]);
    const csv = [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "applications.csv";
    anchor.click();
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
  };

  const openSheets = () => {
    window.open("https://sheets.new", "_blank", "noopener,noreferrer");
    setShowExportMenu(false);
  };

  const boardStatus = isLoading
    ? "Loading your roles…"
    : isError
      ? "Roles unavailable"
      : search
        ? `${filteredItems.length} matching ${filteredItems.length === 1 ? "job" : "jobs"}`
        : `${total} ${total === 1 ? "job" : "jobs"}`;

  const clearFilters = () => setParams({ min: null, found: null, from: null, to: null });
  const commitMatch = () => {
    if (matchDraft == null) return;
    setParams({ min: matchDraft > 0 ? String(matchDraft) : null });
    setMatchDraft(null);
  };
  const dateInput = "h-8 rounded-full bg-card px-3 text-xs text-foreground ring-1 ring-foreground/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-white/[0.03] dark:ring-white/10";
  const pendingCount = pendingDelete?.length ?? 0;

  return (
    <Screen>
      <PageHero
        eyebrow="Your job search"
        title="Application tracker"
        description="Your pipeline, from saved role to signed offer. Keep the next step in sight."
        className="pb-0 md:pb-0"
        actions={
          <>
            <IslandLink href="/jobs" tone="ghost" size="md" icon={<Briefcase size={16} weight="light" />} trailing>
              Find roles
            </IslandLink>
          </>
        }
      />

      <StatStrip
        items={[
          { label: "All roles", value: items.length },
          { label: "In progress", value: activeCount },
          { label: "Interviews", value: interviewCount },
          { label: "Offers", value: offerCount },
        ]}
      />

      <Section aria-label="Applications" className="space-y-5 md:space-y-5">
        <h2 className="sr-only">Applications</h2>

        <Bezel size="md" coreClassName="flex min-w-0 flex-wrap items-center gap-3 p-3">
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search company or role" aria-label="Search applications" trayClassName="w-full sm:flex-1 sm:min-w-[12rem]" leading={<MagnifyingGlass size={16} weight="light" />} trailing={search ? <IconButton size="sm" aria-label="Clear search" onClick={() => setSearch("")}><X size={13} weight="light" /></IconButton> : undefined} />
          <ExportMenu open={showExportMenu} onOpenChange={setShowExportMenu} onDownloadCsv={exportToCSV} onOpenSheets={openSheets} />
        </Bezel>

        <Bezel size="md" coreClassName="space-y-3 p-3">
          <div role="group" aria-label="Match filter" className="flex flex-wrap items-center gap-2">
            <span className="w-20 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Match</span>
            {MATCH_CHIPS.map((chip) => (
              <Chip key={chip.value} active={minMatch === chip.value} onClick={() => setParams({ min: chip.value ? String(chip.value) : null })}>{chip.label}</Chip>
            ))}
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={matchDraft ?? minMatch}
              aria-label="Minimum match percent"
              onChange={(event) => setMatchDraft(Number(event.target.value))}
              onPointerUp={commitMatch}
              onKeyUp={commitMatch}
              onBlur={commitMatch}
              className="h-1.5 w-32 accent-primary"
            />
            <span className="w-10 font-geist-mono text-xs tabular-nums text-muted-foreground">≥{matchDraft ?? minMatch}%</span>
          </div>
          <div role="group" aria-label="Found date filter" className="flex flex-wrap items-center gap-2">
            <span className="w-20 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Found</span>
            {FOUND_CHIPS.map((chip) => (
              <Chip key={chip.value} active={found === chip.value} onClick={() => setParams(chip.value === "any" ? { found: null, from: null, to: null } : { found: chip.value })}>{chip.label}</Chip>
            ))}
            {found === "custom" ? (
              <>
                <input type="date" aria-label="Found from" value={from} max={to || undefined} onChange={(event) => setParams({ from: event.target.value || null })} className={dateInput} />
                <span aria-hidden className="text-xs text-muted-foreground">to</span>
                <input type="date" aria-label="Found until" value={to} min={from || undefined} onChange={(event) => setParams({ to: event.target.value || null })} className={dateInput} />
              </>
            ) : null}
          </div>
        </Bezel>

        <Reveal subtle className="flex flex-wrap items-center justify-between gap-3">
          <p aria-live="polite" className="flex items-center gap-2 pl-1 text-[13px] text-muted-foreground">
            <ArrowsLeftRight size={15} weight="light" aria-hidden />
            <span className="tabular-nums">{boardStatus}</span>
          </p>
          {checkedIds.length > 0 ? (
            <IslandButton tone="danger" size="sm" icon={<Trash size={14} />} onClick={() => setPendingDelete(checkedIds)}>
              Delete {checkedIds.length} selected
            </IslandButton>
          ) : (
            <span className="text-xs text-muted-foreground">Select a role to view details</span>
          )}
        </Reveal>

        {isLoading ? (
          <Bezel size="md" aria-busy="true" aria-label="Loading applications" coreClassName="space-y-3 p-4">
            {Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-16 w-full rounded-xl" />)}
          </Bezel>
        ) : isError ? (
          <Reveal>
            <Bezel role="alert" coreClassName="px-4">
              <EmptyPanel
                icon={<WarningCircle size={24} weight="light" />}
                title="Could not load your applications."
                description="The list could not reach the server. Your saved roles are safe."
                action={
                  <IslandButton tone="ghost" size="sm" onClick={() => refetch()}>
                    Try again
                  </IslandButton>
                }
              />
            </Bezel>
          </Reveal>
        ) : items.length === 0 && filtersActive ? (
          <Bezel><EmptyPanel compact title="No jobs match these filters" description="Loosen the match or found-date filter." action={<IslandButton tone="ghost" size="sm" onClick={clearFilters}>Clear filters</IslandButton>} /></Bezel>
        ) : items.length === 0 ? (
          <Reveal>
            <Bezel coreClassName="px-4">
              <EmptyPanel
                icon={<Tray size={24} weight="light" />}
                title="Your tracker is ready"
                description="Save a job from the Jobs page to keep its posting and description here."
                action={
                  <IslandLink href="/jobs" size="md" trailing>
                    Explore jobs
                  </IslandLink>
                }
              />
            </Bezel>
          </Reveal>
        ) : filteredItems.length === 0 ? (
          <Bezel><EmptyPanel compact title="No matching applications" description="Try another company or role." action={<IslandButton tone="ghost" size="sm" onClick={() => setSearch("")}>Clear search</IslandButton>} /></Bezel>
        ) : (
          <ApplicationList
            items={filteredItems}
            onSelect={setSelectedId}
            onStageChange={(id, newStage) => statusMutation.mutate({ id, newStage })}
            checked={checked}
            onCheckedChange={onCheckedChange}
            onDelete={(id) => setPendingDelete([id])}
            sort={sort}
            onSortChange={(next) => setParams({ sort: next === "found_desc" ? null : next })}
          />
        )}
      </Section>

      <ApplicationDrawer
        application={selected}
        open={selected !== null}
        onClose={() => setSelectedId(null)}
        onStageChange={(stage) => selected && statusMutation.mutate({ id: selected.id, newStage: stage })}
        activityRuns={activityRuns}
      />

      <Dialog open={pendingDelete !== null} onOpenChange={(open) => { if (!open && !deleteMutation.isPending) setPendingDelete(null); }}>
        <DialogContent className="w-[calc(100%-2rem)] rounded-3xl border-border bg-card p-5 sm:p-6">
          <DialogTitle>{pendingCount === 1 ? "Delete this application?" : `Delete ${pendingCount} applications?`}</DialogTitle>
          <DialogDescription className="leading-6">
            {pendingCount === 1 ? "It" : "They"} will be removed from your tracker. You can undo right after deleting.
          </DialogDescription>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <IslandButton tone="ghost" size="sm" disabled={deleteMutation.isPending} onClick={() => setPendingDelete(null)}>Cancel</IslandButton>
            <IslandButton tone="danger" size="sm" disabled={deleteMutation.isPending} aria-busy={deleteMutation.isPending} onClick={() => pendingDelete && deleteMutation.mutate(pendingDelete)} icon={deleteMutation.isPending ? <CircleNotch size={14} className="animate-spin" /> : <Trash size={14} />}>
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </IslandButton>
          </div>
        </DialogContent>
      </Dialog>
    </Screen>
  );
}

/** Export trigger with a floating Double-Bezel popover (CSV download / Google Sheets). */
function ExportMenu({
  open,
  onOpenChange,
  onDownloadCsv,
  onOpenSheets,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDownloadCsv: () => void;
  onOpenSheets: () => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) onOpenChange(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpenChange(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onOpenChange]);

  const options = [
    { key: "csv", label: "Download CSV", hint: "Every role on the board as a file", icon: <FileCsv size={17} weight="light" />, onClick: onDownloadCsv, trailing: null },
    { key: "sheets", label: "Open Sheets", hint: "Start a blank Google Sheet", icon: <Table size={17} weight="light" />, onClick: onOpenSheets, trailing: <ArrowSquareOut size={13} weight="light" /> },
  ];

  return (
    <div ref={rootRef} className="relative">
      <IslandButton
        tone="ghost"
        size="sm"
        icon={<Export size={15} weight="light" />}
        trailing={
          <CaretDown
            size={12}
            weight="light"
            className={cn("transition-transform duration-500 ease-vanguard", open && "rotate-180")}
          />
        }
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => onOpenChange(!open)}
      >
        Export
      </IslandButton>

      <AnimatePresence>
        {open ? (
          <motion.div
            id={menuId}
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: -6, scale: 0.97 }}
            animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.98 }}
            transition={reduce ? { duration: 0.15 } : SPRING_SOFT}
            className="absolute right-0 top-full z-20 mt-3 w-[min(17rem,calc(100vw-3rem))] origin-top-right"
          >
            <Bezel size="md" lifted coreClassName="p-1.5">
              <ul className="space-y-0.5">
                {options.map((option) => (
                  <li key={option.key}>
                    <button
                      type="button"
                      onClick={option.onClick}
                      className="group flex w-full items-center gap-3 rounded-[1rem] px-3 py-2.5 text-left transition-colors duration-500 ease-vanguard hover:bg-foreground/[0.04] focus-visible:bg-foreground/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/[0.05] dark:focus-visible:bg-white/[0.05]"
                    >
                      <span aria-hidden className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-foreground/[0.04] text-foreground/80 ring-1 ring-foreground/[0.06] dark:bg-white/[0.05] dark:ring-white/10">
                        {option.icon}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-foreground">{option.label}</span>
                        <span className="block truncate text-xs text-muted-foreground">{option.hint}</span>
                      </span>
                      {option.trailing ? (
                        <span aria-hidden className="text-muted-foreground transition-transform duration-500 ease-vanguard group-hover:-translate-y-[1px] group-hover:translate-x-0.5">
                          {option.trailing}
                        </span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            </Bezel>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
