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
  /** Not purchasable yet — no billing is wired up behind it. Shows a
   * "Coming soon" badge and a disabled CTA instead of linking anywhere. */
  comingSoon?: boolean;
};

export function PricingCard({ tier }: { tier: PricingTier }) {
  const cta = (
    <LiquidGlassButton
      tone={tier.highlighted ? "primary" : "ghost"}
      size="md"
      disabled={tier.comingSoon}
      // The highlighted card is already bg-primary — a same-tone button
      // on top of it disappears with no visible edge. Invert instead:
      // solid light button reads clearly against the green card.
      className={tier.highlighted ? "w-full border-primary-foreground bg-primary-foreground text-primary hover:bg-primary-foreground/90" : "w-full"}
    >
      {tier.comingSoon ? "Coming soon" : tier.ctaLabel}
    </LiquidGlassButton>
  );

  return (
    <motion.div
      {...cardHover}
      className={`flex flex-col rounded-[1.75rem] border p-8 shadow-[0_24px_90px_hsl(var(--background)/0.22)] backdrop-blur-xl ${
        tier.highlighted
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border/80 bg-card/70"
      }`}
    >
      <div className="flex items-center gap-2">
        <div className={`text-sm font-medium ${tier.highlighted ? "text-primary-foreground/65" : "text-muted-foreground"}`}>{tier.name}</div>
        {tier.comingSoon && (
          <span
            className={`rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${
              tier.highlighted
                ? "border-primary-foreground/40 text-primary-foreground/80"
                : "border-border text-muted-foreground"
            }`}
          >
            Coming soon
          </span>
        )}
      </div>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="text-5xl font-medium">{tier.price}</span>
        {tier.cadence && <span className={`text-sm ${tier.highlighted ? "text-primary-foreground/60" : "text-muted-foreground"}`}>/{tier.cadence}</span>}
      </div>
      <p className={`mt-4 text-sm ${tier.highlighted ? "text-primary-foreground/70" : "text-muted-foreground"}`}>{tier.description}</p>
      <ul className="mt-8 space-y-3">
        {tier.features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm">
            <Check className={`mt-0.5 h-4 w-4 ${tier.highlighted ? "text-primary-foreground" : "text-success"}`} />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-8">
        {tier.comingSoon ? cta : <Link href={tier.ctaHref} className="block">{cta}</Link>}
      </div>
    </motion.div>
  );
}
