"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

type Props = {
  label: string;
  value: string | number;
  trend?: { delta: string; direction: "up" | "down" };
  icon?: React.ReactNode;
};

export function MetricCard({ label, value, trend, icon }: Props) {
  return (
    <motion.div
      {...cardHover}
      className="rounded-3xl border border-border bg-card/60 p-6 backdrop-blur"
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        {icon && <div className="text-muted-foreground">{icon}</div>}
      </div>
      <div className="mt-4 text-3xl font-medium">{value}</div>
      {trend && (
        <div className={`mt-2 inline-flex items-center gap-1 text-xs ${
          trend.direction === "up" ? "text-success" : "text-danger"
        }`}>
          {trend.direction === "up" ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
          {trend.delta}
        </div>
      )}
    </motion.div>
  );
}
