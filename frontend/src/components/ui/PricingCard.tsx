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
      className={`flex flex-col rounded-[1.75rem] border p-8 shadow-[0_24px_90px_hsl(var(--background)/0.22)] backdrop-blur-xl ${
        tier.highlighted
          ? "border-foreground bg-foreground text-background"
          : "border-border/80 bg-card/70"
      }`}
    >
      <div className={`text-sm font-medium ${tier.highlighted ? "text-background/65" : "text-muted-foreground"}`}>{tier.name}</div>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="text-5xl font-medium">{tier.price}</span>
        {tier.cadence && <span className={`text-sm ${tier.highlighted ? "text-background/60" : "text-muted-foreground"}`}>/{tier.cadence}</span>}
      </div>
      <p className={`mt-4 text-sm ${tier.highlighted ? "text-background/70" : "text-muted-foreground"}`}>{tier.description}</p>
      <ul className="mt-8 space-y-3">
        {tier.features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm">
            <Check className={`mt-0.5 h-4 w-4 ${tier.highlighted ? "text-background" : "text-success"}`} />
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
