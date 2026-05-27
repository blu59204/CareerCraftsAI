"use client";

import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, ArrowRight } from "lucide-react";
import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

type Props = {
  label: string;
  value: string | number;
  trend?: { delta: string; direction: "up" | "down" };
  icon?: React.ReactNode;
  href?: string;
};

export function MetricCard({ label, value, trend, icon, href }: Props) {
  const inner = (
    <motion.div
      {...cardHover}
      className="group rounded-3xl border border-border bg-card/60 p-6 backdrop-blur"
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <div className="flex items-center gap-1 text-muted-foreground">
          {icon}
          {href && (
            <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
          )}
        </div>
      </div>
      <div className="mt-4 text-3xl font-medium">{value}</div>
      {trend && trend.delta && (
        <div className={`mt-2 inline-flex items-center gap-1 text-xs ${
          trend.direction === "up" ? "text-success" : "text-danger"
        }`}>
          {trend.direction === "up" ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
          {trend.delta}
        </div>
      )}
    </motion.div>
  );

  if (href) {
    return <Link href={href} className="block">{inner}</Link>;
  }
  return inner;
}
