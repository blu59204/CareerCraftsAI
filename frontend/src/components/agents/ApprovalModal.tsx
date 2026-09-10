"use client";
import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { BrowserWorkspace } from "./BrowserWorkspace";
import { useAgentStore } from "@/store/agentStore";

interface Props {
  runId: string;
  action: Record<string, unknown>;
  onApprove: () => void;
  onCancel: () => void;
}

function CharCount({ current, max }: { current: number; max: number }) {
  const pct = Math.min(100, (current / max) * 100);
  return (
    <span
      className={`text-xs tabular-nums ${pct > 90 ? "text-red-400" : pct > 75 ? "text-yellow-400" : "text-muted-foreground"}`}
    >
      {current}/{max}
    </span>
  );
}

export function ApprovalModal({ runId, action, onApprove, onCancel }: Props) {
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editedText, setEditedText] = useState("");
  const actionType = (action.type as string) || "unknown";

  const decide = async (approved: boolean) => {
    setLoading(true);
    try {
      await apiClient.post(`/agents/${runId}/approve`, {
        approved,
        edits: approved && editedText ? { body: editedText } : undefined,
      });
      if (approved) {
        useAgentStore.getState().clearCheckpoint(runId);
        useAgentStore.getState().setRunStatus(runId, "queued");
        toast.success("Action approved");
        onApprove();
      } else {
        useAgentStore.getState().setError(runId, "Cancelled by you");
        toast.info("Action cancelled");
        onCancel();
      }
    } catch {
      toast.error("Failed to process approval");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape" && !editing) onCancel();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent
        className="max-w-2xl max-h-[90vh] overflow-y-auto"
        onKeyDown={handleKeyDown}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Review Required
            <Badge variant="secondary" className="capitalize">
              {actionType.replace(/_/g, " ")}
            </Badge>
          </DialogTitle>
          <DialogDescription>Review before executing this action.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">

          {/* Email preview */}
          {actionType === "send_email" && (
            <div className="space-y-3">
              <div className="grid grid-cols-[60px_1fr] gap-1 text-sm">
                <span className="font-medium text-muted-foreground">To:</span>
                <span className="text-foreground">{String(action.recipient ?? "—")}</span>
                <span className="font-medium text-muted-foreground">Subject:</span>
                <span className="text-foreground">{String(action.subject ?? "—")}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Email Body
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (!editing) setEditedText(String(action.body ?? ""));
                    setEditing(!editing);
                  }}
                >
                  {editing ? "Preview" : "Edit"}
                </Button>
              </div>
              {editing ? (
                <div className="space-y-1">
                  <Textarea
                    value={editedText}
                    onChange={(e) => setEditedText(e.target.value)}
                    className="min-h-48 font-mono text-sm"
                    placeholder="Edit the email body..."
                  />
                  <div className="flex justify-end">
                    <CharCount current={editedText.length} max={1500} />
                  </div>
                </div>
              ) : (
                <div className="max-h-48 overflow-y-auto rounded-xl border border-border bg-background/70 p-4 text-sm whitespace-pre-wrap text-foreground">
                  {String(action.body ?? "—")}
                </div>
              )}
            </div>
          )}

          {/* Resume preview */}
          {actionType === "resume_ready" && (
            <div className="space-y-3">
              {action.ats_score ? (
                <div className="flex items-center gap-3 rounded-xl border border-border bg-background/70 p-3">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
                    <span className="text-lg font-bold text-primary">
                      {(action.ats_score as Record<string, number>).composite_score ?? "—"}
                    </span>
                  </div>
                  <div className="text-sm">
                    <p className="font-medium">ATS Score</p>
                    <p className="text-muted-foreground">
                      Keyword: {(action.ats_score as Record<string, number>).keyword_score ?? "—"} |
                      Readability: {(action.ats_score as Record<string, number>).readability_score ?? "—"} |
                      Format: {(action.ats_score as Record<string, number>).format_score ?? "—"}
                    </p>
                  </div>
                </div>
              ) : null}
              {action.ats_score && (action.ats_score as Record<string, unknown>).missing_keywords ? (
                <div className="flex flex-wrap gap-1">
                  {((action.ats_score as Record<string, unknown>).missing_keywords as string[])?.slice(0, 8).map((kw: string) => (
                    <Badge key={kw} variant="outline" className="text-xs">
                      + {kw}
                    </Badge>
                  ))}
                </div>
              ) : null}
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Resume Draft
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (!editing) setEditedText(String(action.resume_markdown ?? action.resume_text ?? ""));
                    setEditing(!editing);
                  }}
                >
                  {editing ? "Preview" : "Edit"}
                </Button>
              </div>
              {editing ? (
                <div className="space-y-1">
                  <Textarea
                    value={editedText}
                    onChange={(e) => setEditedText(e.target.value)}
                    className="min-h-48 font-mono text-sm"
                    placeholder="Edit the resume draft..."
                  />
                  <div className="flex justify-end">
                    <CharCount current={editedText.length} max={5000} />
                  </div>
                </div>
              ) : (
                <div className="max-h-80 overflow-y-auto rounded-xl border border-border bg-background/70 p-4 text-sm whitespace-pre-wrap text-foreground font-mono">
                  {String(action.resume_markdown ?? action.resume_text ?? "—")}
                </div>
              )}
            </div>
          )}

          {/* LinkedIn edits */}
          {actionType === "linkedin_edits" && (
            <div className="space-y-3">
              <div>
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Headline</span>
                <p className="mt-1 rounded-lg border border-border bg-background/70 p-3 text-sm">{String(action.headline ?? "—")}</p>
              </div>
              <div>
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">About</span>
                <p className="mt-1 rounded-lg border border-border bg-background/70 p-3 text-sm whitespace-pre-wrap">{String(action.about ?? "—")}</p>
              </div>
            </div>
          )}

          {/* Submit application */}
          {actionType === "submit_application" && (
            <div className="space-y-3">
              <div className="grid grid-cols-[80px_1fr] gap-1 text-sm">
                <span className="font-medium text-muted-foreground">Role:</span>
                <span className="text-foreground">{String(action.role ?? "—")}</span>
                <span className="font-medium text-muted-foreground">Company:</span>
                <span className="text-foreground">{String(action.company ?? "—")}</span>
              </div>
              {action.job_url ? (
                <a
                  href={String(action.job_url)}
                  target="_blank"
                  rel="noreferrer"
                  className="block break-all text-sm text-primary underline"
                >
                  {String(action.job_url)}
                </a>
              ) : null}
              {action.message ? (
                <p className="text-sm text-muted-foreground">{String(action.message)}</p>
              ) : null}
              {action.browser_result ? (
                <div className="max-h-40 overflow-y-auto rounded-xl border border-border bg-background/70 p-3 text-sm whitespace-pre-wrap font-mono">
                  {String(action.browser_result)}
                </div>
              ) : null}
            </div>
          )}

          {/* Cover letter */}
          {actionType === "cover_letter_review" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Cover Letter
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (!editing) setEditedText(String(action.body ?? ""));
                    setEditing(!editing);
                  }}
                >
                  {editing ? "Preview" : "Edit"}
                </Button>
              </div>
              {editing ? (
                <div className="space-y-1">
                  <Textarea
                    value={editedText}
                    onChange={(e) => setEditedText(e.target.value)}
                    className="min-h-48 font-mono text-sm"
                  />
                  <CharCount current={editedText.length} max={1500} />
                </div>
              ) : (
                <div className="max-h-64 overflow-y-auto rounded-xl border border-border bg-background/70 p-4 text-sm whitespace-pre-wrap">
                  {String(action.body ?? "—")}
                </div>
              )}
            </div>
          )}

          {/* Search confirmation (NL Search) */}
          {actionType === "search_confirmation" && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                We interpreted your search as:
                <span className="ml-2 font-medium text-foreground">
                  {String(action.original_query ?? "—")}
                </span>
              </p>
              {action.interpretation ? (
                <div className="rounded-xl border border-border bg-background/70 p-4">
                  <pre className="text-xs font-mono whitespace-pre-wrap">
                    {JSON.stringify(action.interpretation, null, 2)}
                  </pre>
                </div>
              ) : null}
            </div>
          )}

          {/* Generic fallback for unknown action types */}
          {["browser_input", "browser_review"].includes(actionType) && <>
            <p className="text-sm">{String(action.message ?? "Review your application")}</p>
            <BrowserWorkspace runId={runId} />
          </>}
          {!["send_email", "resume_ready", "linkedin_edits", "submit_application", "cover_letter_review", "search_confirmation", "browser_input", "browser_review"].includes(actionType) && (
            <div className="max-h-64 overflow-y-auto rounded-xl border border-border bg-background/70 p-4">
              <pre className="text-xs font-mono whitespace-pre-wrap text-foreground">
                {JSON.stringify(action, null, 2)}
              </pre>
            </div>
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <Button
            variant="outline"
            onClick={() => decide(false)}
            disabled={loading}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            onClick={() => decide(true)}
            disabled={loading}
            className="flex-[2]"
          >
            {loading ? "Processing..." : actionType === "browser_input" ? "Continue preparation" : actionType === "browser_review" ? "Approve final submission" : "Approve & Execute"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
