import { HeroA } from "@/components/marketing/HeroA";
import { MarqueeRow } from "@/components/marketing/MarqueeRow";
import { HeroB } from "@/components/marketing/HeroB";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { FeaturesGrid } from "@/components/marketing/FeaturesGrid";
import { PricingSection } from "@/components/marketing/PricingSection";

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
      <MarqueeRow items={CHIPS} />
      <HeroB />
      <HowItWorks />
      <FeaturesGrid />
      <PricingSection />
    </>
  );
}
