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
      className="relative overflow-hidden rounded-3xl border border-border bg-card/60 p-8 text-left"
    >
      <div className="mb-6 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        {icon}
      </div>
      <div className="text-lg font-medium text-foreground">{title}</div>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
    </motion.div>
  );
}
