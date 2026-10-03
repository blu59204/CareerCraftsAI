"use client";

import { FilePdf, UploadSimple } from "@phosphor-icons/react";
import { IslandButton, StatusPill } from "@/components/vanguard";

export interface ResumeListItem {
  id: string;
  filename: string;
  is_primary: boolean;
  ats_score: number | null;
}

/** Every uploaded resume; exactly one is Active. "Set active" re-scores it server-side. */
export function ResumeList({
  docs,
  activatingId,
  uploading,
  onActivate,
  onUpload,
}: {
  docs: ResumeListItem[];
  activatingId: string | null;
  uploading: boolean;
  onActivate: (id: string) => void;
  onUpload: () => void;
}) {
  return (
    <div className="mt-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
          Your resumes ({docs.length})
        </h3>
        <IslandButton
          tone="quiet"
          size="sm"
          disabled={uploading}
          onClick={onUpload}
          icon={<UploadSimple size={14} weight="light" />}
        >
          New resume
        </IslandButton>
      </div>
      <ul className="mt-3 space-y-2">
        {docs.map((doc) => (
          <li
            key={doc.id}
            className="flex items-center justify-between gap-3 rounded-xl px-3 py-2 ring-1 ring-foreground/[0.07] dark:ring-white/10"
          >
            <div className="flex min-w-0 items-center gap-2">
              <FilePdf size={15} weight="light" aria-hidden="true" className="shrink-0 text-muted-foreground" />
              <span className="truncate font-geist-mono text-xs text-foreground" title={doc.filename}>
                {doc.filename}
              </span>
              {doc.ats_score != null && (
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{doc.ats_score}</span>
              )}
            </div>
            {doc.is_primary ? (
              <StatusPill tone="success">Active</StatusPill>
            ) : (
              <IslandButton
                tone="ghost"
                size="sm"
                disabled={activatingId !== null}
                onClick={() => onActivate(doc.id)}
              >
                {activatingId === doc.id ? "Activating…" : "Set active"}
              </IslandButton>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
