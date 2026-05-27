import { PricingSection } from "@/components/marketing/PricingSection";
import { FaqAccordion } from "@/components/marketing/FaqAccordion";

export default function PricingPage() {
  return (
    <>
      <section className="bg-background pt-20 pb-6 text-center">
        <h1 className="mx-auto max-w-3xl px-6 text-5xl font-medium tracking-tight md:text-6xl">
          Simple <span className="font-display text-primary">pricing</span>.
        </h1>
        <p className="mx-auto mt-4 max-w-xl px-6 text-muted-foreground">
          Pay for the platform, not the tokens. Your keys cover the LLM costs.
        </p>
      </section>
      <PricingSection />
      <section className="bg-background pb-28">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mb-10 text-center">
            <div className="text-sm text-muted-foreground">FAQ</div>
            <h2 className="mt-2 text-3xl font-medium md:text-4xl">Common questions</h2>
          </div>
          <FaqAccordion />
        </div>
      </section>
    </>
  );
}
