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
      className="relative overflow-hidden rounded-3xl border border-white/10 bg-[#0d0d12] p-8 text-left"
    >
      <div className="mb-6 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/15 text-primary">
        {icon}
      </div>
      <div className="text-lg font-medium text-white">{title}</div>
      <p className="mt-2 text-sm text-white/60">{description}</p>
    </motion.div>
  );
}
