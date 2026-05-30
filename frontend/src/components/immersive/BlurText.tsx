"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";

interface BlurTextProps {
  text: string;
  className?: string;
  delay?: number;
}

export function BlurText({ text, className, delay = 0.055 }: BlurTextProps) {
  return (
    <span className={cn("inline-block", className)} aria-label={text}>
      {text.split(" ").map((word, index) => (
        <motion.span
          aria-hidden
          key={`${word}-${index}`}
          initial={{ opacity: 0, y: 32, filter: "blur(12px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.62, delay: index * delay, ease: [0.16, 1, 0.3, 1] }}
          className="inline-block pr-[0.22em]"
        >
          {word}
        </motion.span>
      ))}
    </span>
  );
}
