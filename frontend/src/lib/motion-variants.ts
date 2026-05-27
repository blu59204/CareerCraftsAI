import type { Variants } from "motion/react";

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: "easeOut" } },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.18 } },
};

export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};

export const cardHover = {
  whileHover: { scale: 1.02, transition: { duration: 0.15 } },
};

export const slideRight: Variants = {
  hidden: { opacity: 0, x: -10 },
  show: { opacity: 1, x: 0, transition: { duration: 0.2 } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.97 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.2, ease: "easeOut" } },
};

export const fadeUpBlur: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.28, ease: [0.22, 1, 0.36, 1] } },
};

export const slideIn: Variants = {
  hidden: { opacity: 0, x: -14 },
  show: { opacity: 1, x: 0, transition: { duration: 0.22, ease: "easeOut" } },
};

export const containerStagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};
