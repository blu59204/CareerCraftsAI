"use client";

import { motion } from "motion/react";
import { BlurText } from "./BlurText";
import { cn } from "@/lib/utils";

interface CommandHeaderProps {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function CommandHeader({ eyebrow, title, description, actions, className }: CommandHeaderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.44, ease: [0.16, 1, 0.3, 1] }}
      className={cn("flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between", className)}
    >
      <div className="max-w-3xl">
        <p className="text-xs uppercase tracking-[0.32em] text-muted-foreground">{eyebrow}</p>
        <h1 className="mt-3 font-display text-5xl leading-[0.9] tracking-tight text-foreground md:text-7xl">
          <BlurText text={title} />
        </h1>
        {description && (
          <p className="mt-5 max-w-2xl text-sm leading-7 text-muted-foreground md:text-base">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </motion.div>
  );
}
