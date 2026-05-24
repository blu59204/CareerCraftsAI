const STEPS = [
  { n: "01", title: "Upload your resume", body: "Drop a PDF or DOCX. We parse skills, projects, and experience." },
  { n: "02", title: "Add a target role", body: "Tell us the role, locations, and seniority. We build a job search plan." },
  { n: "03", title: "Agents go to work", body: "Resume tailoring, job search, application drafts — all in parallel." },
  { n: "04", title: "Approve and send", body: "You stay in the loop. Every email and apply goes through your approval." },
];

export function HowItWorks() {
  return (
    <section id="how" className="relative bg-[#070612] py-28 text-white">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-14 max-w-2xl">
          <div className="text-sm text-white/50">How it works</div>
          <h2 className="mt-2 text-4xl font-medium md:text-5xl">From resume to interview in 4 steps.</h2>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <div key={s.n} className="rounded-3xl border border-white/10 bg-white/[0.02] p-6 liquid-glass">
              <div className="text-xs text-primary">{s.n}</div>
              <div className="mt-3 text-lg font-medium">{s.title}</div>
              <p className="mt-2 text-sm text-white/60">{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
