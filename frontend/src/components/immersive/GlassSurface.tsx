"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface GlassSurfaceProps {
  children: React.ReactNode;
  className?: string;
  tone?: "default" | "strong" | "command";
  interactive?: boolean;
}

export function GlassSurface({
  children,
  className,
  tone = "default",
  interactive = false,
}: GlassSurfaceProps) {
  return (
    <motion.div
      whileHover={interactive ? { y: -3, scale: 1.005 } : undefined}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "glass-panel rounded-[28px]",
        tone === "strong" && "glass-panel-strong",
        tone === "command" && "glass-command",
        interactive && "depth-hover",
        className,
      )}
    >
      {children}
    </motion.div>
  );
}
