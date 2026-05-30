"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

export function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <motion.div
      {...cardHover}
      className="group relative overflow-hidden rounded-2xl border border-border bg-card p-8 text-left shadow-[0_12px_40px_hsl(var(--foreground)/0.06)] transition hover:bg-background"
    >
      <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-primary/35 to-transparent opacity-0 transition group-hover:opacity-100" />
      <div className="mb-6 inline-flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-muted text-primary">
        {icon}
      </div>
      <div className="text-lg font-medium text-foreground">{title}</div>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">{description}</p>
    </motion.div>
  );
}
