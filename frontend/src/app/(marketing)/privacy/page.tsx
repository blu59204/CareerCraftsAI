export const metadata = { title: "Privacy Policy — CareerCraft AI" };

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">Legal</div>
      <h1 className="text-4xl font-medium">Privacy Policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated: September 26, 2026</p>

      <div className="mt-10 space-y-8 text-muted-foreground leading-relaxed">
        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">What we collect</h2>
          <p>
            Information you provide directly: your name, email address, phone number, LinkedIn URL,
            resume and other uploaded document content, job preferences, and saved job
            applications (including job descriptions you save). API keys you supply for
            third-party AI providers are encrypted (AES-256-GCM) at rest and never stored in
            plaintext. If you use the browser-extension auto-apply feature, your LinkedIn sign-in
            credentials are stored encrypted the same way, solely so the extension can act on your
            behalf in your own browser — we do not read them in plaintext, and you can delete them
            at any time.
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
            Data is stored in a self-hosted PostgreSQL database. Resume and document text is also
            embedded into a vector index (pgvector), tied to your account, so agents can retrieve
            relevant context — this embedding is stored alongside your account and is deleted with
            it. Your resume and agent outputs are stored in your account namespace and accessible
            only to you.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Third parties we use</h2>
          <p>
            <strong className="text-foreground">Clerk</strong> handles sign-in and issues the
            session cookie described below. <strong className="text-foreground">
              Your own configured AI provider
            </strong>{" "}
            (OpenAI, Anthropic, Google, or others you connect) receives the content needed to run
            the agent you invoke — for example your resume text when tailoring a resume. If you
            connect Gmail or Google Drive, that access goes through{" "}
            <strong className="text-foreground">Nango</strong>, a credential broker; we never see
            your Google password. Interview-prep video suggestions link to YouTube thumbnail
            images only — no video is embedded on the page, and no YouTube cookie is set unless
            you click through to youtube.com.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Cookies</h2>
          <p>
            We use session cookies for authentication only (set by Clerk, our sign-in provider). No
            advertising or third-party tracking cookies are used. See our{" "}
            <a href="/cookies" className="text-primary hover:underline">
              Cookie Policy
            </a>{" "}
            for the full list.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Your rights</h2>
          <p>
            You may request deletion of your account and all associated data at any time from
            Settings → Account → Danger zone.
          </p>
          <p className="mt-3">
            If you're in India, under the Digital Personal Data Protection Act, 2023 you have the
            right to access a summary of your personal data and the processing we do with it, to
            correct or update it, to have it erased once it's no longer needed for the purpose you
            gave it for, and to file a grievance with us — and, if unresolved, with the Data
            Protection Board of India.
          </p>
          <p className="mt-3">
            If you're in the EEA, UK, or a jurisdiction with similar data-protection law, you also
            have the right to access, correct, or export your data, and to object to or restrict
            certain processing. Contact us using the details below for either.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Children</h2>
          <p>
            CareerCraft AI is not directed at children under 16, and we do not knowingly collect
            data from them. If you believe a child has created an account, contact us and we will
            remove it.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Contact</h2>
          <p>
            Questions? Email us at{" "}
            <a href="mailto:privacy@careercraftsai.me" className="text-primary hover:underline">
              privacy@careercraftsai.me
            </a>
            .
          </p>
          <p className="mt-3 text-sm">
            {/* Not yet a registered company/LLP — operating as an unregistered business under
                the trade name "CareerCraft". TODO: add the street-level address, and once
                incorporated, replace this with the registered entity name and CIN/LLPIN. */}
            CareerCraft, Bangalore, Karnataka, India.
          </p>
        </section>
      </div>
    </div>
  );
}
