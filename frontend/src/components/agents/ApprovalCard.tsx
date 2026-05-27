"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

type Props = {
  title: string;
  summary: string;
  onApprove: () => void;
  onReject: () => void;
};

export function ApprovalCard({ title, summary, onApprove, onReject }: Props) {
  return (
    <motion.div {...cardHover} className="rounded-3xl border border-warning/30 bg-warning/5 p-5">
      <div className="text-sm font-medium">{title}</div>
      <p className="mt-2 text-sm text-muted-foreground">{summary}</p>
      <div className="mt-4 flex gap-2">
        <LiquidGlassButton tone="primary" size="sm" onClick={onApprove}>
          Approve
        </LiquidGlassButton>
        <LiquidGlassButton tone="ghost" size="sm" onClick={onReject}>
          Reject
        </LiquidGlassButton>
      </div>
    </motion.div>
  );
}
