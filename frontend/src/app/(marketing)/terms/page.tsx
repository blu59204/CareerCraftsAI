export const metadata = { title: "Terms of Service — CareerCraft AI" };

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">Legal</div>
      <h1 className="text-4xl font-medium">Terms of Service</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated: May 2026</p>

      <div className="mt-10 space-y-8 text-muted-foreground leading-relaxed">
        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">1. Acceptance</h2>
          <p>
            By using CareerCraft AI you agree to these terms. If you do not agree, do not use the
            platform.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">2. Your account</h2>
          <p>
            You are responsible for maintaining the security of your account and credentials. Do
            not share your API keys or login details with others.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">3. Acceptable use</h2>
          <p>
            CareerCraft AI automates legitimate job search activities. You must not use the platform
            for spam, harassment, or to violate the terms of service of third-party platforms
            (LinkedIn, job boards, etc.). Browser automation features use human-like delays to
            comply with platform policies.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">4. API keys</h2>
          <p>
            You supply your own API keys for AI providers. Usage costs are billed directly by those
            providers. CareerCraft AI is not responsible for charges incurred through your usage.
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
          <h2 className="mb-3 text-lg font-medium text-foreground">6. Changes</h2>
          <p>
            We may update these terms at any time. Continued use of the platform constitutes
            acceptance of updated terms.
          </p>
        </section>
      </div>
    </div>
  );
}
