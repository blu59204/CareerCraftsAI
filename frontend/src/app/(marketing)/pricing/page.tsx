import type { Metadata } from "next";
import { PricingSection } from "@/components/marketing/PricingSection";
import { FaqAccordion } from "@/components/marketing/FaqAccordion";
import { JsonLd } from "@/components/seo/JsonLd";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Pay for the platform, not the tokens — bring your own AI provider key. Free tier available now; Pro and Team plans coming soon.",
  alternates: { canonical: "/pricing" },
};

// Only the Free tier is a real, currently-purchasable offer — Pro and Team
// are marked "Coming soon" on the page itself with no billing behind them
// yet, so they're deliberately left out here rather than claimed as
// available.
const SOFTWARE_APPLICATION_JSON_LD = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "CareerCraft AI",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  offers: {
    "@type": "Offer",
    name: "Free",
    price: "0",
    priceCurrency: "USD",
  },
};

export default function PricingPage() {
  return (
    <>
      <JsonLd data={SOFTWARE_APPLICATION_JSON_LD} />
      <section className="bg-background pt-20 pb-6 text-center">
        <div className="mx-auto max-w-3xl px-6 text-left">
          <Breadcrumbs trail={[{ name: "Pricing", href: "/pricing" }]} />
        </div>
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
