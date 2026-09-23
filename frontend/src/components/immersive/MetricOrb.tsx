"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface MetricOrbProps {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  href?: string;
  accent?: "primary" | "success" | "warning" | "danger";
}

const accentMap = {
  primary: "from-primary/35 to-accent/20 text-primary",
  success: "from-success/30 to-primary/15 text-success",
  warning: "from-warning/30 to-primary/15 text-warning",
  danger: "from-danger/30 to-primary/15 text-danger",
};

export function MetricOrb({ label, value, icon, href, accent = "primary" }: MetricOrbProps) {
  const body = (
    <motion.div
      initial={{ opacity: 0, y: 18, filter: "blur(8px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      whileHover={{ y: -4, rotateX: 2, rotateY: -2 }}
      transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
      className="glass-panel depth-hover group relative min-h-[132px] overflow-hidden rounded-[28px] p-5"
    >
      <div className={cn("absolute -right-10 -top-10 h-32 w-32 rounded-full bg-gradient-to-br blur-2xl", accentMap[accent])} />
      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">{label}</p>
          <p className="mt-4 font-display text-5xl leading-none text-foreground">{value}</p>
        </div>
        {icon && (
          <div className={cn("glow-primary flex h-11 w-11 items-center justify-center rounded-2xl bg-card/70", accentMap[accent])}>
            {icon}
          </div>
        )}
      </div>
      <div className="absolute bottom-4 left-5 right-5 h-px bg-gradient-to-r from-transparent via-primary/35 to-transparent" />
    </motion.div>
  );

  return href ? <Link href={href}>{body}</Link> : body;
}
