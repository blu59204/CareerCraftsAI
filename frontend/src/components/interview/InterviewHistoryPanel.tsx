"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CircleNotch, ClockCounterClockwise } from "@phosphor-icons/react";
import { apiClient } from "@/lib/api";
import {
  reviewRows,
  scoreTrend,
  type InterviewSessionDetail,
  type InterviewSessionItem,
} from "@/lib/interview-history";
import { Bezel, Notice, PanelTitle, StatusPill } from "@/components/vanguard";
import { ScoreRing, scoreTone } from "./ScoreRing";

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function SessionReview({ id }: { id: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["interview-session", id],
    queryFn: () => apiClient.get<InterviewSessionDetail>(`/interview/session/${id}/summary`).then((r) => r.data),
  });
  if (isLoading) {
    return (
      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <CircleNotch size={14} className="animate-spin" aria-hidden /> Loading answers…
      </p>
    );
  }
  if (isError || !data) return <Notice tone="danger">Couldn&rsquo;t load this session.</Notice>;
  return (
    <ol className="space-y-5">
      {reviewRows(data).map((row) => (
        <li key={row.index} className="space-y-1.5">
          <p className="text-sm font-medium text-foreground">
            {row.index + 1}. {row.question}
          </p>
          {row.answer === null ? (
            <p className="text-xs text-muted-foreground">Not answered.</p>
          ) : (
            <>
              <p className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{row.answer}</p>
              {row.score !== null ? (
                <StatusPill tone={scoreTone(row.score)}>{row.score} / 100</StatusPill>
              ) : null}
            </>
          )}
        </li>
      ))}
    </ol>
  );
}

/** Past mock interviews with scores, and each session's answers on demand. */
export function InterviewHistoryPanel() {
  const [openId, setOpenId] = useState<string | null>(null);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["interview-sessions"],
    queryFn: () => apiClient.get<InterviewSessionItem[]>("/interview/sessions").then((r) => r.data),
  });

  if (isLoading) {
    return (
      <Notice icon={<CircleNotch size={15} className="animate-spin" />}>Loading your past sessions…</Notice>
    );
  }
  if (isError) return <Notice tone="danger">Couldn&rsquo;t load your interview history.</Notice>;
  if (!data || data.length === 0) {
    return (
      <Notice icon={<ClockCounterClockwise size={15} weight="light" />}>
        No mock interviews yet. Finish a session and it will show up here with your scores.
      </Notice>
    );
  }

  const trend = scoreTrend(data);
  return (
    <div className="space-y-4">
      <PanelTitle
        title="Past sessions"
        icon={<ClockCounterClockwise size={16} weight="light" />}
        meta={
          trend === null
            ? `${data.length} session${data.length === 1 ? "" : "s"}`
            : `${trend >= 0 ? "+" : ""}${trend} points since your first completed session`
        }
      />
      <ul className="space-y-3">
        {data.map((session) => {
          const open = openId === session.id;
          return (
            <li key={session.id}>
              <Bezel size="md" coreClassName="p-5">
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => setOpenId(open ? null : session.id)}
                  className="flex w-full items-center gap-4 text-left"
                >
                  {session.overall_score !== null ? (
                    <ScoreRing value={session.overall_score} size={52} tone={scoreTone(session.overall_score)} />
                  ) : (
                    <span className="grid h-[52px] w-[52px] place-items-center rounded-full text-xs text-muted-foreground ring-1 ring-foreground/10">
                      —
                    </span>
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-foreground">
                      {session.role}
                      {session.company ? ` · ${session.company}` : ""}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {formatDate(session.started_at)} · {session.answered_count} of {session.question_count} answered
                    </span>
                  </span>
                  <StatusPill tone={session.status === "completed" ? "success" : "neutral"}>
                    {session.status === "completed" ? "Completed" : "In progress"}
                  </StatusPill>
                </button>
                {open ? (
                  <div className="mt-5 border-t border-foreground/[0.06] pt-5">
                    <SessionReview id={session.id} />
                  </div>
                ) : null}
              </Bezel>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
