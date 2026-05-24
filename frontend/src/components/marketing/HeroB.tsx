export function HeroB() {
  return (
    <section className="border-y border-border bg-card/50 py-24">
      <div className="mx-auto max-w-5xl px-6 text-center">
        <h2 className="text-balance text-5xl font-medium leading-tight md:text-7xl">
          <span className="font-display text-primary">Craft</span> the career you want.
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-muted-foreground">
          Built for students, freshers, and career-switchers who refuse to send the same resume twice.
        </p>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-x-10 gap-y-4 text-sm text-muted-foreground">
          <span>Trusted by students at</span>
          <span className="opacity-80">IIT</span>
          <span className="opacity-80">NIT</span>
          <span className="opacity-80">BITS</span>
          <span className="opacity-80">IIIT</span>
          <span className="opacity-80">VIT</span>
        </div>
      </div>
    </section>
  );
}
