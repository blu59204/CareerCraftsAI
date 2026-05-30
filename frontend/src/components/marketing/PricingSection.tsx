import { PricingCard, type PricingTier } from "@/components/ui/PricingCard";

const TIERS: PricingTier[] = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    description: "Get started with resume tools and 5 AI runs per week.",
    features: ["Resume ATS scoring", "Job match preview", "5 agent runs / week", "BYOK API keys"],
    ctaHref: "/register",
    ctaLabel: "Start free",
  },
  {
    name: "Pro",
    price: "$12",
    cadence: "month",
    description: "Full automation for an active job hunt.",
    features: [
      "Unlimited agent runs",
      "LinkedIn + Naukri search",
      "Email drafting + send",
      "Follow-up sequencing",
      "Application kanban",
    ],
    ctaHref: "/register?plan=pro",
    ctaLabel: "Go Pro",
    highlighted: true,
  },
  {
    name: "Team",
    price: "Custom",
    description: "For bootcamps and university placement cells.",
    features: ["Everything in Pro", "Cohort management", "Bulk seats", "Shared templates", "Priority support"],
    ctaHref: "/contact",
    ctaLabel: "Talk to us",
  },
];

export function PricingSection() {
  return (
    <section id="pricing" className="relative overflow-hidden bg-background py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div className="relative mb-14 text-center">
          <div className="inline-flex rounded-full border border-border bg-card/70 px-3 py-1 text-xs uppercase tracking-[0.22em] text-muted-foreground">
            SaaS Pricing Flow
          </div>
          <h2 className="mx-auto mt-5 max-w-2xl text-4xl font-medium leading-tight md:text-5xl">
            Simple plans. Your keys. Your costs.
          </h2>
        </div>
        <div className="relative grid gap-4 md:grid-cols-3">
          {TIERS.map((t) => (
            <PricingCard key={t.name} tier={t} />
          ))}
        </div>
      </div>
    </section>
  );
}
