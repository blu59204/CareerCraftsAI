export function HeroB() {
  return (
    <section className="relative overflow-hidden border-y border-border bg-card py-28 text-foreground">
      <div className="absolute inset-0 bg-[linear-gradient(90deg,hsl(var(--border)/0.45)_1px,transparent_1px),linear-gradient(0deg,hsl(var(--border)/0.35)_1px,transparent_1px)] bg-[length:72px_72px] [mask-image:radial-gradient(ellipse_70%_70%_at_50%_45%,black,transparent_82%)]" />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <div className="inline-flex rounded-full border border-border bg-muted px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Grow AI Talent Platform reference
          </div>
          <h2 className="mt-6 text-balance font-display text-5xl leading-[0.95] md:text-7xl">
            Craft career moves with agent-level precision.
          </h2>
          <p className="mt-6 max-w-xl text-base leading-8 text-muted-foreground">
            Built for students, freshers, and career-switchers who need resume fit, location-aware search, safe outreach, and a clean tracker in one command workspace.
          </p>
        </div>
        <div className="rounded-[2rem] border border-border bg-background p-3 shadow-[0_24px_80px_hsl(var(--foreground)/0.08)]">
          <div className="rounded-[1.5rem] border border-border bg-card p-5">
            <div className="mb-5 flex items-center justify-between">
              <span className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Talent Pipeline</span>
              <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">Live</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              {["Resume", "Jobs", "Outreach"].map((item, index) => (
                <div key={item} className="rounded-2xl border border-border bg-background p-4">
                  <div className="text-xs text-muted-foreground">{item}</div>
                  <div className="mt-3 h-2 rounded-full bg-muted">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${84 - index * 13}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 space-y-2">
              {["Frontend Intern - Bengaluru hybrid", "Junior AI Engineer - Remote", "Product Analyst - Pune onsite"].map((job) => (
                <div key={job} className="flex items-center justify-between rounded-xl border border-border bg-background px-4 py-3 text-sm">
                  <span className="text-foreground">{job}</span>
                  <span className="font-medium text-primary">Match</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
