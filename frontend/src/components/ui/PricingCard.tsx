"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";
import { LiquidGlassButton } from "./LiquidGlassButton";

export type PricingTier = {
  name: string;
  price: string;
  cadence?: string;
  description: string;
  features: string[];
  ctaHref: string;
  ctaLabel: string;
  highlighted?: boolean;
};

export function PricingCard({ tier }: { tier: PricingTier }) {
  return (
    <motion.div
      {...cardHover}
      className={`flex flex-col rounded-3xl border p-8 ${
        tier.highlighted
          ? "border-primary/40 bg-primary/[0.06] shadow-xl"
          : "border-border bg-card"
      }`}
    >
      <div className="text-sm font-medium text-muted-foreground">{tier.name}</div>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="text-5xl font-medium">{tier.price}</span>
        {tier.cadence && <span className="text-sm text-muted-foreground">/{tier.cadence}</span>}
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{tier.description}</p>
      <ul className="mt-8 space-y-3">
        {tier.features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm">
            <Check className="mt-0.5 h-4 w-4 text-success" />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-8">
        <Link href={tier.ctaHref} className="block">
          <LiquidGlassButton
            tone={tier.highlighted ? "primary" : "ghost"}
            size="md"
            className="w-full"
          >
            {tier.ctaLabel}
          </LiquidGlassButton>
        </Link>
      </div>
    </motion.div>
  );
}
