"use client";

import { useState, type DragEvent, type KeyboardEvent } from "react";
import { motion } from "motion/react";
import { ClockCountdown, DotsSixVertical, MapPin } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { Bezel, RevealGroup, Select, StatusPill, listItem, listStagger, type StatusTone } from "@/components/vanguard";

export type AppStage = "saved" | "applied" | "viewed" | "interview" | "offer" | "rejected";

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
  notes?: string | null;
};

/** Board order of the pipeline stages. */
export const APP_STAGES: AppStage[] = ["saved", "applied", "viewed", "interview", "offer", "rejected"];

export const STAGE_LABELS: Record<AppStage, string> = {
  saved: "Saved",
  applied: "Applied",
  viewed: "Viewed",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

/** Semantic tone of each stage (status pills, column markers). */
export const STAGE_TONE: Record<AppStage, StatusTone> = {
  saved: "neutral",
  applied: "primary",
  viewed: "neutral",
  interview: "warning",
  offer: "success",
  rejected: "danger",
};

const STAGE_DOT: Record<AppStage, string> = {
  saved: "bg-muted-foreground/50",
  applied: "bg-primary",
  viewed: "bg-foreground/40 dark:bg-white/40",
  interview: "bg-warning",
  offer: "bg-success",
  rejected: "bg-danger/70",
};

/** Hostname of a saved posting URL, or null when it is missing / not http(s). */
export function sourceLabel(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) return null;
    return parsed.hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function monogram(company: string): string {
  const match = company.match(/[\p{L}\p{N}]/u);
  return match ? match[0].toUpperCase() : "·";
}

type Props = {
  items: ApplicationItem[];
  onSelect: (id: string) => void;
  /** Called when a card is dropped on a different stage column. */
  onStageChange?: (id: string, newStage: AppStage) => void;
  /** Copy shown inside a column with no cards (e.g. "No matching roles" while searching). */
  emptyColumnLabel?: string;
};

/**
 * Horizontally scrollable pipeline board. Each stage is a recessed
 * Double-Bezel column and a native HTML5 drop target; cards are draggable
 * and open the application drawer on click / Enter / Space.
 */
export function ApplicationKanban({ items, onSelect, onStageChange, emptyColumnLabel = "No roles yet" }: Props) {
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverStage, setDragOverStage] = useState<AppStage | null>(null);

  const handleDragStart = (event: DragEvent<HTMLDivElement>, id: string) => {
    setDraggedId(id);
    event.dataTransfer.effectAllowed = "move";
    // Firefox only starts a drag when the payload is set.
    event.dataTransfer.setData("text/plain", id);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>, targetStage: AppStage) => {
    event.preventDefault();
    if (draggedId) {
      const item = items.find((candidate) => candidate.id === draggedId);
      if (item && item.stage !== targetStage) {
        onStageChange?.(draggedId, targetStage);
      }
    }
    setDraggedId(null);
    setDragOverStage(null);
  };

  const clearDrag = () => {
    setDraggedId(null);
    setDragOverStage(null);
  };

  return (
    <RevealGroup
      className="flex min-w-0 max-w-full snap-x snap-proximity gap-3 overflow-x-auto overscroll-x-contain p-1 pb-5 [scrollbar-width:thin] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label="Pipeline stages"
      role="list"
      tabIndex={0}
    >
      {APP_STAGES.map((stage) => {
        const columnItems = items.filter((item) => item.stage === stage);
        const isOver = dragOverStage === stage;
        return (
          <motion.div key={stage} variants={listItem} role="listitem" className="w-[min(17.25rem,100%)] shrink-0 snap-start md:w-[18.5rem]">
            <Bezel
              size="md"
              tone="muted"
              data-column-status={stage}
              onDragOver={(event) => {
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                setDragOverStage(stage);
              }}
              onDragLeave={() => setDragOverStage((current) => (current === stage ? null : current))}
              onDrop={(event) => handleDrop(event, stage)}
              className={cn(
                "h-full rounded-3xl transition-[background-color,box-shadow] duration-500 ease-vanguard",
                isOver && "bg-primary/[0.07] ring-primary/40 dark:bg-primary/[0.08] dark:ring-primary/40",
              )}
              coreClassName={cn(
                "flex min-h-[24rem] flex-col p-2.5 transition-colors duration-500 ease-vanguard",
                isOver && "bg-primary/[0.04] dark:bg-primary/[0.05]",
              )}
            >
              <div className="flex items-center gap-2.5 px-2 pb-3 pt-2">
                <span aria-hidden className={cn("h-2 w-2 shrink-0 rounded-full", STAGE_DOT[stage])} />
                <h3 className="font-geist text-[13px] font-semibold tracking-[-0.01em] text-foreground">{STAGE_LABELS[stage]}</h3>
                <span className="rounded-full bg-foreground/[0.06] px-2 py-0.5 font-geist-mono text-[11px] tabular-nums text-muted-foreground dark:bg-white/[0.08]">
                  {columnItems.length}
                </span>
              </div>

              {columnItems.length === 0 ? (
                <p
                  className={cn(
                    "grid flex-1 place-items-center rounded-[1.1rem] border border-dashed px-3 py-10 text-center text-xs text-muted-foreground transition-colors duration-500 ease-vanguard",
                    isOver ? "border-primary/40 text-primary" : "border-foreground/[0.1] dark:border-white/10",
                  )}
                >
                  {isOver ? "Drop to move here" : emptyColumnLabel}
                </p>
              ) : (
                <motion.div variants={listStagger} className="flex flex-1 flex-col gap-2.5">
                  {columnItems.map((item) => (
                    <motion.div key={item.id} variants={listItem}>
                      <ApplicationCard
                        item={item}
                        dragging={draggedId === item.id}
                        onSelect={onSelect}
                        onDragStart={handleDragStart}
                        onDragEnd={clearDrag}
                      />
                    </motion.div>
                  ))}
                </motion.div>
              )}
            </Bezel>
          </motion.div>
        );
      })}
    </RevealGroup>
  );
}

/** Compact table on desktop, labeled cards on phones. */
export function ApplicationList({ items, onSelect, onStageChange }: Props) {
  return (
    <Bezel size="md" coreClassName="overflow-hidden">
      <table role="table" className="application-table w-full table-fixed text-left text-sm">
        <caption className="sr-only">Applications and their next steps</caption>
        <thead className="bg-muted/40 text-[11px] uppercase tracking-wider text-muted-foreground">
          <tr>
            <th scope="col" className="w-[40%] px-4 py-3 font-medium">Role / company</th>
            <th scope="col" className="w-[25%] px-4 py-3 font-medium">Stage</th>
            <th scope="col" className="w-[15%] px-4 py-3 font-medium">Match</th>
            <th scope="col" className="w-[20%] px-4 py-3 font-medium">Follow-up</th>
          </tr>
        </thead>
        <tbody role="rowgroup" className="divide-y divide-border">
          {items.map((item) => (
            <tr role="row" key={item.id} className="transition-colors hover:bg-muted/30">
              <td role="cell" className="px-4 py-3 align-middle">
                <button type="button" onClick={() => onSelect(item.id)} className="block w-full min-w-0 rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <span className="block truncate font-medium text-foreground">{item.role}</span>
                  <span className="mt-1 block truncate text-xs text-muted-foreground">{item.company}{item.location ? ` · ${item.location}` : ""}</span>
                </button>
              </td>
              <td role="cell" data-label="Stage" className="px-4 py-3 align-middle">
                {onStageChange ? (
                  <Select aria-label={`Stage for ${item.role} at ${item.company}`} value={item.stage} onChange={(event) => onStageChange(item.id, event.target.value as AppStage)} className="h-9 px-2 pr-7 text-xs">
                    {APP_STAGES.map((stage) => <option key={stage} value={stage}>{STAGE_LABELS[stage]}</option>)}
                  </Select>
                ) : <StatusPill tone={STAGE_TONE[item.stage]}>{STAGE_LABELS[item.stage]}</StatusPill>}
              </td>
              <td role="cell" data-label="Match" className="px-4 py-3 align-middle font-geist-mono tabular-nums text-primary">{item.matchPercent != null ? `${item.matchPercent}%` : "—"}</td>
              <td role="cell" data-label="Follow-up" className="px-4 py-3 align-middle text-xs text-muted-foreground">{item.nextFollowUp ?? "Not scheduled"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Bezel>
  );
}

function ApplicationCard({
  item,
  dragging,
  onSelect,
  onDragStart,
  onDragEnd,
}: {
  item: ApplicationItem;
  dragging: boolean;
  onSelect: (id: string) => void;
  onDragStart: (event: DragEvent<HTMLDivElement>, id: string) => void;
  onDragEnd: () => void;
}) {
  const source = sourceLabel(item.jobUrl);
  const meta = [item.location, source].filter(Boolean).join(" · ");
  const match = item.matchPercent != null ? Math.max(0, Math.min(100, item.matchPercent)) : null;

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(item.id);
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      data-testid="application-card"
      aria-label={[
        `${item.role} at ${item.company}`,
        match != null ? `${item.matchPercent}% match` : null,
        item.nextFollowUp ? `follow up ${item.nextFollowUp}` : null,
        "open details or drag to another stage",
      ]
        .filter(Boolean)
        .join(", ")}
      onDragStart={(event) => onDragStart(event, item.id)}
      onDragEnd={onDragEnd}
      onClick={() => onSelect(item.id)}
      onKeyDown={handleKeyDown}
      className={cn(
        "group relative block w-full cursor-grab select-none rounded-[1.15rem] bg-card p-4 text-left ring-1 ring-foreground/[0.06] shadow-bezel-core dark:ring-white/[0.08] dark:shadow-bezel-core-dark",
        "transition-[transform,box-shadow,opacity] duration-500 ease-vanguard hover:-translate-y-0.5 hover:shadow-ambient-sm active:cursor-grabbing",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60",
        dragging && "scale-[0.98] opacity-40",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-foreground/[0.04] font-geist text-[13px] font-semibold text-foreground/70 ring-1 ring-foreground/[0.06] dark:bg-white/[0.05] dark:ring-white/10"
        >
          {monogram(item.company)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className="min-w-0 truncate text-sm font-medium tracking-[-0.01em] text-foreground">{item.company}</span>
            {match != null && (
              <span className="shrink-0 font-geist-mono text-[11px] tabular-nums text-primary">{item.matchPercent}%</span>
            )}
          </div>
          <p className="mt-1 line-clamp-2 text-[13px] leading-5 text-muted-foreground">{item.role}</p>
        </div>
      </div>

      {match != null && (
        <div aria-hidden className="mt-4 h-[3px] overflow-hidden rounded-full bg-foreground/[0.06] dark:bg-white/[0.08]">
          <div className="h-full origin-left rounded-full bg-primary/80" style={{ transform: `scaleX(${match / 100})` }} />
        </div>
      )}

      {(meta || item.nextFollowUp) && (
        <div className="mt-3 space-y-2 pr-5">
          {meta && (
            <p className="flex min-w-0 items-center gap-1.5 text-[11px] text-muted-foreground">
              <MapPin size={12} weight="light" aria-hidden className="shrink-0" />
              <span className="truncate">{meta}</span>
            </p>
          )}
          {item.nextFollowUp && (
            <p className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-medium text-primary ring-1 ring-primary/20">
              <ClockCountdown size={12} weight="light" aria-hidden />
              Follow up {item.nextFollowUp}
            </p>
          )}
        </div>
      )}

      <DotsSixVertical
        size={14}
        weight="light"
        aria-hidden
        className="absolute bottom-3 right-3 text-muted-foreground opacity-0 transition-opacity duration-500 ease-vanguard group-hover:opacity-70"
      />
    </div>
  );
}
