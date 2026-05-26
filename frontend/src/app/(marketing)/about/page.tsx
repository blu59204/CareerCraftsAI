import Link from "next/link";

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">About</div>
      <h1 className="text-4xl font-medium">Built for job seekers.</h1>
      <p className="mt-4 text-lg text-muted-foreground">
        CareerCraft AI is a multi-agent job search platform that helps you tailor resumes, discover
        matching roles, and follow up with recruiters — automatically.
      </p>

      <div className="mt-12 space-y-10">
        <section>
          <h2 className="text-xl font-medium">Our mission</h2>
          <p className="mt-3 text-muted-foreground leading-relaxed">
            Job hunting is broken. Hours wasted on generic applications, ignored follow-ups, and
            one-size-fits-all resumes. We built CareerCraft AI to give every candidate an unfair
            advantage — the kind that used to require a personal career coach.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-medium">How it works</h2>
          <p className="mt-3 text-muted-foreground leading-relaxed">
            You bring your API keys and your resume. Our agents handle the rest — scanning job
            boards, tailoring application materials, optimizing your LinkedIn profile, and keeping
            your outreach timely and personal.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-medium">Privacy-first</h2>
          <p className="mt-3 text-muted-foreground leading-relaxed">
            Your data is yours. We never train on your personal information, and your API keys are
            encrypted at rest. Read our{" "}
            <Link href="/privacy" className="text-primary hover:underline">
              privacy policy
            </Link>{" "}
            for details.
          </p>
        </section>
      </div>

      <div className="mt-16">
        <Link
          href="/register"
          className="inline-flex h-10 items-center rounded-full bg-primary px-6 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Get started free
        </Link>
      </div>
    </div>
  );
}
