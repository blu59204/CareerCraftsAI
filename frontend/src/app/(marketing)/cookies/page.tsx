export const metadata = { title: "Cookie Policy — CareerCraft AI" };

const COOKIES = [
  {
    name: "__session / __client (and similar)",
    setBy: "Clerk (our sign-in provider)",
    purpose: "Keeps you signed in. Strictly necessary — the app cannot authenticate you without it.",
    lifespan: "Session / a few days, per Clerk's own policy.",
  },
];

export default function CookiesPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">Legal</div>
      <h1 className="text-4xl font-medium">Cookie Policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated: September 26, 2026</p>

      <div className="mt-10 space-y-8 text-muted-foreground leading-relaxed">
        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">What we actually use</h2>
          <p>
            CareerCraft AI sets exactly one category of cookie today: the session cookie our
            sign-in provider, Clerk, uses to keep you logged in. We do not run any analytics,
            advertising, or third-party tracking scripts, so no other cookie is set by this site.
            If that ever changes, this page — and the banner shown on your first visit — will be
            updated to ask for your consent before any non-essential cookie is set.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">The cookie, in detail</h2>
          <div className="mt-2 overflow-x-auto rounded-2xl border border-border">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="bg-muted/50 text-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Cookie</th>
                  <th className="px-4 py-3 font-medium">Set by</th>
                  <th className="px-4 py-3 font-medium">Purpose</th>
                  <th className="px-4 py-3 font-medium">Lifespan</th>
                </tr>
              </thead>
              <tbody>
                {COOKIES.map((c) => (
                  <tr key={c.name} className="border-t border-border align-top">
                    <td className="px-4 py-3 font-mono text-xs">{c.name}</td>
                    <td className="px-4 py-3">{c.setBy}</td>
                    <td className="px-4 py-3">{c.purpose}</td>
                    <td className="px-4 py-3">{c.lifespan}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Why no consent banner is required</h2>
          <p>
            Under GDPR/ePrivacy and similar laws, cookies that are strictly necessary to provide a
            service you asked for — like staying signed in — don't require opt-in consent, only
            disclosure. That's this cookie. We still show a one-time notice on your first visit so
            this is never hidden from you.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">Managing cookies</h2>
          <p>
            You can block or delete cookies in your browser settings, but doing so will sign you
            out and prevent CareerCraft AI from keeping you signed in.
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
        </section>
      </div>
    </div>
  );
}
