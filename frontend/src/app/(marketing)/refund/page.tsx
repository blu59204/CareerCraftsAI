export const metadata = { title: "Refund Policy — CareerCraft AI" };

export default function RefundPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">Legal</div>
      <h1 className="text-4xl font-medium">Refund Policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated: September 26, 2026</p>

      <div className="mt-10 space-y-8 text-muted-foreground leading-relaxed">
        <section className="rounded-2xl border border-warning/30 bg-warning/10 p-4 text-sm">
          <p className="text-foreground">
            <strong>Right now, no paid CareerCraft AI plan can be purchased.</strong> The Pro and
            Team tiers on our{" "}
            <a href="/pricing" className="text-primary hover:underline">
              pricing page
            </a>{" "}
            are marked "Coming soon" and have no billing behind them yet. The policy below is a
            draft of what will apply once a paid plan launches, published in advance for
            transparency — it will be reviewed and finalized before anyone is actually charged.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">1. Free tier</h2>
          <p>
            The Free plan costs nothing and is not subject to any refund process — there's nothing
            to refund.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">2. Cancelling a subscription</h2>
          <p>
            You will be able to cancel a paid plan at any time from Settings → Account → Billing.
            Cancelling stops future renewals; you keep access through the end of the billing period
            you already paid for.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">3. Refunds</h2>
          <p>
            Subscriptions are billed in advance for the coming period and, once launched, are
            expected to be non-refundable for that period once it has started — the same model used
            by most monthly SaaS products. Two exceptions we intend to honor:
          </p>
          <ul className="mt-3 list-inside list-disc space-y-1">
            <li>A duplicate or clearly mistaken charge (contact us and we'll correct it).</li>
            <li>
              A billing error caused by us — for example, being charged after you cancelled, or for
              a plan you didn't select.
            </li>
          </ul>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">4. Provider costs are separate</h2>
          <p>
            CareerCraft AI is bring-your-own-key: any usage costs billed by your configured AI
            provider (OpenAI, Anthropic, Google, etc.) are between you and that provider, are never
            collected by us, and are not covered by this policy.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-medium text-foreground">5. How to request one</h2>
          <p>
            Once billing exists, email{" "}
            <a href="mailto:billing@careercraftsai.me" className="text-primary hover:underline">
              billing@careercraftsai.me
            </a>{" "}
            with your account email and the charge in question.
          </p>
        </section>
      </div>
    </div>
  );
}
