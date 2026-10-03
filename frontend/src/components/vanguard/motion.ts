import type { Transition, Variants } from "motion/react";

/**
 * Vanguard motion tokens. Every redesigned screen pulls its easing and
 * entrance choreography from here — never `linear` / `easeInOut`.
 */

/** Heavy, mass-simulating ease used for UI state changes. */
export const EASE_VANGUARD = [0.32, 0.72, 0, 1] as const;
/** Long-tail deceleration used for entrances. */
export const EASE_OUT_EXPO = [0.16, 1, 0.3, 1] as const;

/** Spring for pills, segmented indicators and toggles. */
export const SPRING_SOFT: Transition = { type: "spring", stiffness: 380, damping: 36, mass: 0.9 };
/** Slower spring for panels, drawers and overlays. */
export const SPRING_PANEL: Transition = { type: "spring", stiffness: 260, damping: 32, mass: 1 };

/**
 * Every blur entrance must END at `filter: none`, not `blur(0px)`. Any
 * non-`none` filter creates a stacking context (and a containing block for
 * fixed children), which traps descendant dropdowns/popovers under later
 * sibling cards regardless of their z-index. `transitionEnd` drops the filter
 * once the entrance finishes.
 */
export const FILTER_CLEAR = { filter: "none" } as const;

/**
 * When scroll entrances fire: as soon as any part of the element is within
 * 15% of the bottom of the viewport. Waiting for a share of it to be well
 * inside left sections that only peeked into view invisible, which read as
 * blank space at the bottom of every page until the user scrolled.
 */
export const REVEAL_VIEWPORT = { once: true, amount: 0, margin: "0px 0px 15% 0px" } as const;

/** Heavy fade-up with a short blur resolve (≈850ms). */
export const reveal: Variants = {
  hidden: { opacity: 0, y: 40, filter: "blur(10px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.85, ease: EASE_OUT_EXPO },
    transitionEnd: FILTER_CLEAR,
  },
};

/** Same as `reveal` but without translation — for large surfaces. */
export const revealFade: Variants = {
  hidden: { opacity: 0, filter: "blur(8px)" },
  show: { opacity: 1, filter: "blur(0px)", transition: { duration: 0.8, ease: EASE_OUT_EXPO }, transitionEnd: FILTER_CLEAR },
};

/** Parent orchestrator for staggered children. */
export const revealStagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.04 } },
};

/** Tight stagger for lists (rows, chips, cards inside a column). */
export const listStagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.035 } },
};

/** List item entrance (lighter than `reveal`). */
export const listItem: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE_OUT_EXPO } },
};

/** Tab/panel swap — use with <AnimatePresence mode="wait">. */
export const panelSwap: Variants = {
  hidden: { opacity: 0, y: 12, filter: "blur(6px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.55, ease: EASE_OUT_EXPO }, transitionEnd: FILTER_CLEAR },
  exit: { opacity: 0, y: -8, filter: "blur(4px)", transition: { duration: 0.25, ease: EASE_VANGUARD } },
};
