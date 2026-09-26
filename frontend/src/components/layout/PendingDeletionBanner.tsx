"use client";

import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useUserStatus } from "@/components/auth/UserStatusContext";

function daysRemaining(scheduledFor: string): number {
  const ms = new Date(scheduledFor).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

export function PendingDeletionBanner() {
  const { status, refresh } = useUserStatus();
  const [cancelling, setCancelling] = useState(false);

  if (!status?.deletion_requested_at || !status.deletion_scheduled_for) return null;

  const days = daysRemaining(status.deletion_scheduled_for);
  const scheduledDate = new Date(status.deletion_scheduled_for).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  async function handleCancel() {
    if (cancelling) return;
    setCancelling(true);
    try {
      await apiClient.post("/users/me/cancel-deletion");
      toast.success("Account deletion cancelled");
      refresh();
    } catch {
      toast.error("Couldn't cancel deletion — please try again");
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-danger/30 bg-danger/10 px-6 py-3 text-sm md:px-8">
      <div className="flex items-center gap-2 text-foreground">
        <AlertTriangle className="h-4 w-4 shrink-0 text-danger" />
        <span>
          Your account is scheduled for deletion on <strong>{scheduledDate}</strong> ({days}{" "}
          {days === 1 ? "day" : "days"} left).
        </span>
      </div>
      <button
        type="button"
        disabled={cancelling}
        onClick={handleCancel}
        className="rounded-full bg-danger px-4 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-danger/90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {cancelling ? "Cancelling…" : "Cancel deletion"}
      </button>
    </div>
  );
}
