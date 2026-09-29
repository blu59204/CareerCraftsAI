"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowUpRight,
  BriefcaseBusiness,
  CalendarDays,
  Clock3,
  ExternalLink,
  FileText,
  Mail,
  MapPin,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { setPendingJd } from "@/lib/job-handoff";
import type { ApplicationItem, AppStage } from "./ApplicationKanban";

type AgentRun = {
  id: string;
  agent_type: string;
  status: string;
  started_at: string;
  output_summary?: string;
};

type Props = {
  application: ApplicationItem | null;
  open: boolean;
  onClose: () => void;
  onStageChange: (stage: AppStage) => void;
  activityRuns: AgentRun[];
};

const STAGES: AppStage[] = ["saved", "applied", "viewed", "interview", "offer", "rejected"];
const STAGE_LABELS: Record<AppStage, string> = {
  saved: "Saved",
  applied: "Applied",
  viewed: "Viewed",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

const AI_SUGGESTIONS: Partial<Record<AppStage, { label: string; copy: string; href: string }>> = {
  interview: {
    label: "Prepare for interview",
    copy: "Practice role specific questions and plan your stories.",
    href: "/interview-prep",
  },
  offer: {
    label: "Review compensation",
    copy: "Compare your offer with market data and prepare negotiation points.",
    href: "/salary",
  },
};

function safeSource(url: string | null | undefined): { href: string; label: string } | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (!["https:", "http:"].includes(parsed.protocol)) return null;
    return { href: parsed.href, label: parsed.hostname.replace(/^www\./, "") };
  } catch {
    return null;
  }
}

function dateLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? null
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function ApplicationDrawer({ application, open, onClose, onStageChange, activityRuns }: Props) {
  const router = useRouter();
  if (!application) return null;

  const source = safeSource(application.jobUrl);
  const suggestion = AI_SUGGESTIONS[application.stage];
  const appliedDate = dateLabel(application.appliedAt);

  function customizeResume() {
    const current = application;
    if (!current?.jobDescription?.trim()) {
      toast.error("This saved role has no description to tailor against.");
      return;
    }
    setPendingJd({
      jdText: current.jobDescription,
      role: current.role,
      company: current.company,
    });
    onClose();
    router.push("/resume");
  }

  return (
    <Dialog.Root open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-sm" />
        <Dialog.Content
          aria-describedby="application-details-description"
          className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-border bg-background shadow-2xl sm:max-w-xl"
        >
          <header className="border-b border-border px-5 pb-5 pt-6 sm:px-7">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="mb-3 flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <BriefcaseBusiness className="h-3.5 w-3.5" />
                  Application details
                </div>
                <Dialog.Title className="text-balance font-command text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
                  {application.role}
                </Dialog.Title>
                <Dialog.Description id="application-details-description" className="mt-1 text-sm text-muted-foreground">
                  {application.company}
                  {application.matchPercent != null && <> <span aria-hidden="true">·</span> {application.matchPercent}% match</>}
                </Dialog.Description>
              </div>
              <Dialog.Close asChild>
                <button
                  type="button"
                  aria-label="Close application details"
                  className="rounded-lg p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                >
                  <X className="h-4 w-4" />
                </button>
              </Dialog.Close>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-2">
              {application.location && (
                <div className="flex min-w-0 items-center gap-2 rounded-xl border border-border bg-card/60 px-3 py-2.5">
                  <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="truncate text-sm">{application.location}</span>
                </div>
              )}
              {appliedDate && (
                <div className="flex items-center gap-2 rounded-xl border border-border bg-card/60 px-3 py-2.5">
                  <CalendarDays className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="text-sm">Applied {appliedDate}</span>
                </div>
              )}
            </div>
          </header>

          <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5 sm:px-7">
            <section className="rounded-2xl border border-primary/20 bg-primary/[0.04] p-4">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-primary/10 p-2 text-primary">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="font-semibold">Make this resume fit the role</h2>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {application.jobDescription
                      ? "Use this job description to tailor your resume and check its match."
                      : "Add the job description to this role before tailoring a resume."}
                  </p>
                  <LiquidGlassButton
                    type="button"
                    tone="primary"
                    size="sm"
                    className="mt-3"
                    disabled={!application.jobDescription?.trim()}
                    onClick={customizeResume}
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    Customize resume for this job
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </LiquidGlassButton>
                </div>
              </div>
            </section>

            <section>
              <div className="mb-2 flex items-center gap-2">
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold">Original source</h2>
              </div>
              {source ? (
                <a
                  href={source.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-center justify-between gap-3 rounded-xl border border-border bg-card/50 p-3 transition hover:border-primary/40 hover:bg-card"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{source.label}</span>
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">{source.href}</span>
                  </span>
                  <ExternalLink className="h-4 w-4 shrink-0 text-muted-foreground transition group-hover:text-primary" />
                </a>
              ) : (
                <p className="rounded-xl border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
                  Original posting link was not saved for this role.
                </p>
              )}
            </section>

            <section>
              <div className="mb-2 flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold">Job description</h2>
              </div>
              {application.jobDescription?.trim() ? (
                <div className="max-h-[26rem] overflow-y-auto rounded-xl border border-border bg-card/40 p-4">
                  <p className="whitespace-pre-wrap text-sm leading-6 text-foreground/90">{application.jobDescription}</p>
                </div>
              ) : (
                <p className="rounded-xl border border-dashed border-border px-3 py-4 text-sm leading-6 text-muted-foreground">
                  This listing has no saved description. Open the original source to review the details.
                </p>
              )}
            </section>

            <section className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-xs font-medium text-muted-foreground">Application stage</span>
                <select
                  value={application.stage}
                  onChange={(event) => onStageChange(event.target.value as AppStage)}
                  className="h-10 w-full rounded-xl border border-border bg-card px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
                >
                  {STAGES.map((stage) => <option key={stage} value={stage}>{STAGE_LABELS[stage]}</option>)}
                </select>
              </label>
              {application.nextFollowUp && (
                <div>
                  <span className="mb-1.5 block text-xs font-medium text-muted-foreground">Next follow-up</span>
                  <div className="flex h-10 items-center gap-2 rounded-xl border border-border bg-card px-3 text-sm">
                    <Clock3 className="h-4 w-4 text-muted-foreground" />
                    {application.nextFollowUp}
                  </div>
                </div>
              )}
            </section>

            {application.notes && (
              <section>
                <h2 className="mb-2 text-sm font-semibold">Notes</h2>
                <p className="whitespace-pre-wrap rounded-xl border border-border bg-card/40 p-4 text-sm leading-6 text-muted-foreground">{application.notes}</p>
              </section>
            )}

            {suggestion && (
              <section className="rounded-2xl border border-border bg-card/50 p-4">
                <p className="text-xs font-medium text-muted-foreground">Next step</p>
                <p className="mt-1 text-sm">{suggestion.copy}</p>
                <Link href={suggestion.href} onClick={onClose} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline">
                  {suggestion.label} <ArrowUpRight className="h-3.5 w-3.5" />
                </Link>
              </section>
            )}

            <section className="pb-2">
              <div className="mb-3 flex items-center gap-2">
                <Clock3 className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold">Recent activity</h2>
              </div>
              {activityRuns.length ? (
                <ol className="space-y-3 border-l border-border pl-4">
                  {activityRuns.map((run) => (
                    <li key={run.id} className="relative text-sm">
                      <span className="absolute -left-[1.32rem] top-1.5 h-2 w-2 rounded-full bg-primary ring-4 ring-background" />
                      <p className="font-medium capitalize">{run.agent_type.replace(/_/g, " ")}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {run.status} · {new Date(run.started_at).toLocaleString()}
                      </p>
                      {run.output_summary && <p className="mt-1 text-xs leading-5 text-muted-foreground">{run.output_summary}</p>}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm text-muted-foreground">No agent activity is linked to this role yet.</p>
              )}
            </section>
          </div>

          <footer className="border-t border-border bg-background/95 px-5 py-4 sm:px-7">
            <Link href="/email" onClick={onClose} className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition hover:text-foreground">
              <Mail className="h-4 w-4" /> Draft a follow-up email
            </Link>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
