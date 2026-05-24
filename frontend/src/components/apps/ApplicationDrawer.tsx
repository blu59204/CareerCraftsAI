"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import type { ApplicationItem } from "./ApplicationKanban";

type Props = {
  application: ApplicationItem | null;
  open: boolean;
  onClose: () => void;
};

export function ApplicationDrawer({ application, open, onClose }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm" />
        <Dialog.Content className="fixed right-0 top-0 z-50 h-full w-full max-w-md overflow-y-auto border-l border-border bg-card p-6">
          {application && (
            <>
              <div className="flex items-start justify-between">
                <div>
                  <Dialog.Title className="text-xl font-medium">{application.role}</Dialog.Title>
                  <Dialog.Description className="text-sm text-muted-foreground">{application.company}</Dialog.Description>
                </div>
                <button onClick={onClose} className="rounded-full p-2 hover:bg-muted" aria-label="Close">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-6 space-y-4">
                <div className="rounded-2xl border border-border p-4">
                  <div className="text-xs text-muted-foreground">Match score</div>
                  <div className="mt-1 text-2xl font-medium">{application.matchPercent}%</div>
                </div>
                <div className="rounded-2xl border border-border p-4">
                  <div className="text-xs text-muted-foreground">Stage</div>
                  <div className="mt-1 text-sm">{application.stage}</div>
                </div>
                <div className="rounded-2xl border border-border p-4">
                  <div className="text-xs text-muted-foreground">Draft email</div>
                  <textarea
                    className="mt-2 w-full rounded-xl border border-border bg-background p-3 text-sm"
                    rows={5}
                    placeholder="Compose follow-up…"
                  />
                  <div className="mt-3 flex gap-2">
                    <LiquidGlassButton tone="primary" size="sm">Send</LiquidGlassButton>
                    <LiquidGlassButton tone="ghost" size="sm">Save draft</LiquidGlassButton>
                  </div>
                </div>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
