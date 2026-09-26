export const metadata = { title: "Terms of Service — CareerCraft AI" };

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">Legal</div>
      <h1 className="text-4xl font-medium">Terms of Service</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated: September 26, 2026</p>

      <div className="mt-10 space-y-8 text-muted-foreground leading-relaxed">
        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">1. Acceptance</h2>
          <p>
            By creating an account or using CareerCraft AI you agree to these terms and to our{" "}
            <a href="/privacy" className="text-primary hover:underline">
              Privacy Policy
            </a>
            . If you do not agree, do not use the platform. You must be at least 16 years old to
            create an account.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">2. Your account</h2>
          <p>
            You are responsible for maintaining the security of your account and credentials. Do
            not share your API keys or login details with others. You may delete your account at
            any time from Settings → Account → Danger zone; we may suspend or terminate an account
            that violates these terms.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">3. Acceptable use</h2>
          <p>
            CareerCraft AI automates legitimate job search activities. You must not use the platform
            for spam, harassment, or to violate the terms of service of third-party platforms
            (LinkedIn, job boards, etc.). Browser automation features use human-like delays to
            comply with platform policies, and every application requires your explicit approval
            before it submits.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">4. API keys and paid features</h2>
          <p>
            You supply your own API keys for AI providers. Usage costs are billed directly by those
            providers. CareerCraft AI is not responsible for charges incurred through your usage.
            Any paid CareerCraft AI subscription plan is governed by our{" "}
            <a href="/refund" className="text-primary hover:underline">
              Refund Policy
            </a>
            . Plans shown as "Coming soon" on our pricing page are not currently available for
            purchase.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">5. Limitation of liability</h2>
          <p>
            CareerCraft AI is provided as-is. We are not liable for job outcomes, missed
            opportunities, or decisions made based on AI-generated content.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">6. Governing law</h2>
          <p>
            {/* TODO: fill in the operator's actual jurisdiction before relying on this page. */}
            [Governing law and jurisdiction to be added here.]
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">7. Changes</h2>
          <p>
            We may update these terms at any time. Material changes will update the date above;
            continued use of the platform after a change constitutes acceptance of the updated
            terms.
          </p>
        </section>
      </div>
    </div>
  );
}
