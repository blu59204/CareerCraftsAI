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
import { toast } from "sonner";
import { apiClient } from "@/lib/api";

interface Props {
  runId: string;
  action: Record<string, unknown>;
  onApprove: () => void;
  onCancel: () => void;
}

export function ApprovalModal({ runId, action, onApprove, onCancel }: Props) {
  const [loading, setLoading] = useState(false);
  const actionType = action.type as string;

  const decide = async (approved: boolean) => {
    setLoading(true);
    try {
      await apiClient.post(`/agents/${runId}/approve`, { approved });
      approved ? toast.success("Action approved") : toast.info("Action cancelled");
      approved ? onApprove() : onCancel();
    } catch {
      toast.error("Failed to process approval");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Review Required{" "}
            <Badge variant="secondary">{actionType?.replace(/_/g, " ")}</Badge>
          </DialogTitle>
          <DialogDescription>Review before executing.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2 text-sm">
          {actionType === "send_email" && (
            <>
              <div>
                <span className="font-medium">To:</span> {action.recipient as string}
              </div>
              <div>
                <span className="font-medium">Subject:</span> {action.subject as string}
              </div>
              <div className="bg-slate-50 rounded p-3 whitespace-pre-wrap max-h-48 overflow-y-auto">
                {action.body as string}
              </div>
            </>
          )}
          {actionType === "resume_ready" && (
            <div className="bg-slate-50 rounded p-3 whitespace-pre-wrap max-h-64 overflow-y-auto">
              {action.resume_text as string}
            </div>
          )}
          {actionType === "linkedin_edits" && (
            <div className="space-y-2">
              <div>
                <span className="font-medium">Headline:</span> {action.headline as string}
              </div>
              <p className="text-slate-600">
                {(action.about as string)?.slice(0, 200)}...
              </p>
            </div>
          )}
        </div>
        <div className="flex gap-2 pt-2">
          <Button
            onClick={() => decide(true)}
            disabled={loading}
            className="flex-1"
          >
            {loading ? "Processing..." : "Approve & Execute"}
          </Button>
          <Button
            variant="outline"
            onClick={() => decide(false)}
            disabled={loading}
          >
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
