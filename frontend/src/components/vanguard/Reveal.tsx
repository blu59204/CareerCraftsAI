"use client";

import { motion, useReducedMotion, type HTMLMotionProps } from "motion/react";
import { cn } from "@/lib/utils";
import { reveal, revealStagger, listItem } from "./motion";

type RevealProps = HTMLMotionProps<"div"> & {
  /** Delay in seconds before the entrance starts. */
  delay?: number;
  /** Use a lighter list-item entrance instead of the heavy section reveal. */
  subtle?: boolean;
};

/**
 * Scroll-triggered heavy fade-up (IntersectionObserver via `whileInView`).
 * Fires once; collapses to a plain fade under prefers-reduced-motion.
 */
export function Reveal({ delay = 0, subtle = false, className, children, ...props }: RevealProps) {
  const reduce = useReducedMotion();
  const base = subtle ? listItem : reveal;
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.15, margin: "0px 0px -8% 0px" }}
      variants={
        reduce
          ? { hidden: { opacity: 0 }, show: { opacity: 1, transition: { duration: 0.2 } } }
          : {
              hidden: base.hidden,
              show: {
                ...(base.show as object),
                transition: { ...((base.show as { transition?: object }).transition ?? {}), delay },
              },
            }
      }
      className={cn(className)}
      {...props}
    >
      {children}
    </motion.div>
  );
}

/** Parent that staggers any `motion` children using the `hidden`/`show` variant names. */
export function RevealGroup({ className, children, ...props }: HTMLMotionProps<"div">) {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.1 }}
      variants={revealStagger}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}
