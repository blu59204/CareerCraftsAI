export const metadata = { title: "Privacy Policy — CareerCraft AI" };

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">Legal</div>
      <h1 className="text-4xl font-medium">Privacy Policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated: May 2026</p>

      <div className="mt-10 space-y-8 text-muted-foreground leading-relaxed">
        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">What we collect</h2>
          <p>
            We collect the information you provide directly — your name, email address, resume
            content, and job preferences. We also collect API keys you supply for third-party
            providers (encrypted AES-256 at rest, never stored in plaintext).
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">How we use it</h2>
          <p>
            Your data is used solely to operate the CareerCraft AI platform on your behalf. We run
            agents using the models and credentials you configure. We do not sell, share, or train
            on your personal data.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Data storage</h2>
          <p>
            Data is stored in Supabase (PostgreSQL) hosted on AWS infrastructure. Your resume and
            agent outputs are stored in your account namespace and accessible only to you.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Cookies</h2>
          <p>
            We use session cookies for authentication only. No advertising or third-party tracking
            cookies are used.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Your rights</h2>
          <p>
            You may request deletion of your account and all associated data at any time from
            Settings → Account → Danger zone.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Contact</h2>
          <p>
            Questions? Email us at{" "}
            <a href="mailto:privacy@careercraft.ai" className="text-primary hover:underline">
              privacy@careercraft.ai
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
