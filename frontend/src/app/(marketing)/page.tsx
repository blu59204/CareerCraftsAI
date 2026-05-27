import { HeroA } from "@/components/marketing/HeroA";
import { MarqueeRow } from "@/components/marketing/MarqueeRow";
import { HeroB } from "@/components/marketing/HeroB";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { FeaturesGrid } from "@/components/marketing/FeaturesGrid";
import { PricingSection } from "@/components/marketing/PricingSection";
import { FaqAccordion } from "@/components/marketing/FaqAccordion";

const CHIPS = [
  "Resume AI",
  "Job Match",
  "Email Agent",
  "Application Tracker",
  "BYOK Models",
  "ATS Optimizer",
  "Follow-up Agent",
];

export default function Home() {
  return (
    <>
      <HeroA />
      <MarqueeRow items={CHIPS} doubleRow />
      <HeroB />
      <HowItWorks />
      <FeaturesGrid />
      <PricingSection />
      <section className="bg-muted/30 py-20">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mb-10 text-center">
            <div className="text-sm font-medium text-primary">FAQ</div>
            <h2 className="mt-2 text-3xl font-medium md:text-4xl">Questions? Answered.</h2>
          </div>
          <FaqAccordion />
        </div>
      </section>
    </>
  );
}
