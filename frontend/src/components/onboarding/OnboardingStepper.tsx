"use client";

import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";

type Step = { id: string; title: string; content: ReactNode };

type Props = {
  steps: Step[];
  currentIndex: number;
  onChange: (i: number) => void;
};

export function OnboardingStepper({ steps, currentIndex, onChange }: Props) {
  const current = steps[currentIndex];
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-10">
      <div className="flex items-center gap-2">
        {steps.map((s, i) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onChange(i)}
            aria-label={`Go to step ${i + 1}`}
            className={`h-2 rounded-full transition-all ${
              i === currentIndex ? "w-8 bg-primary" : "w-2 bg-muted"
            }`}
          />
        ))}
      </div>
      <div className="text-center">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">
          Step {currentIndex + 1} of {steps.length}
        </div>
        <h2 className="mt-2 text-3xl font-medium">{current.title}</h2>
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={current.id}
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 }}
          transition={{ duration: 0.3 }}
          className="w-full"
        >
          {current.content}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
