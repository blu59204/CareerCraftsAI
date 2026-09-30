"use client";

import { useState } from "react";
import { Check, HandPalm } from "@phosphor-icons/react";
import { IslandButton } from "@/components/vanguard";

type Props = {
  title: string;
  summary: string;
  /** May return a promise; the buttons stay disabled until it settles so a decision can't be sent twice. */
  onApprove: () => void | Promise<void>;
  onReject: () => void | Promise<void>;
};

/**
 * Human-in-the-loop decision row. Rendered inside the dashboard's approvals
 * panel: a warm warning-tinted inset surface (not a nested card) with the
 * action summary and an Approve / Reject pair.
 */
export function ApprovalCard({ title, summary, onApprove, onReject }: Props) {
  const [pending, setPending] = useState<"approve" | "reject" | null>(null);

  const decide = (kind: "approve" | "reject") => {
    if (pending) return;
    setPending(kind);
    Promise.resolve(kind === "approve" ? onApprove() : onReject()).finally(() => setPending(null));
  };

  return (
    <article
      aria-busy={pending !== null}
      className="rounded-[1.25rem] bg-warning/[0.06] p-4 ring-1 ring-warning/20 transition-colors duration-500 ease-vanguard hover:bg-warning/[0.09]"
    >
      <div className="flex items-start gap-3">
        <span aria-hidden className="relative mt-1.5 flex h-2 w-2 shrink-0">
          <span className="absolute inset-0 animate-ping rounded-full bg-warning opacity-60 motion-reduce:hidden" />
          <span className="relative h-2 w-2 rounded-full bg-warning" />
        </span>
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-medium capitalize tracking-[-0.01em] text-foreground">{title}</h4>
          <p className="mt-1 line-clamp-2 text-[13px] leading-5 text-muted-foreground">{summary}</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 pl-5">
        <IslandButton
          size="sm"
          tone="primary"
          disabled={pending !== null}
          onClick={() => decide("approve")}
          icon={<Check size={14} weight="light" />}
        >
          {pending === "approve" ? "Approving…" : "Approve"}
        </IslandButton>
        <IslandButton
          size="sm"
          tone="quiet"
          disabled={pending !== null}
          onClick={() => decide("reject")}
          icon={<HandPalm size={14} weight="light" />}
        >
          {pending === "reject" ? "Rejecting…" : "Reject"}
        </IslandButton>
      </div>
    </article>
  );
}
