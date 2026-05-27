import Link from "next/link";

export const metadata = { title: "Documentation — CareerCraft AI" };

const SECTIONS = [
  {
    title: "Getting started",
    items: ["Quick start guide", "Connect your first AI provider", "Upload your resume", "Configure job preferences"],
  },
  {
    title: "Agents",
    items: ["Resume Agent", "Job Search Agent", "Email Agent", "LinkedIn Agent", "Follow-up Agent"],
  },
  {
    title: "Integrations",
    items: ["Supabase Auth setup", "Google OAuth (Gmail)", "LinkedIn OIDC", "OpenAI & Anthropic keys"],
  },
  {
    title: "Self-hosting",
    items: ["Docker Compose deployment", "Environment variables", "Database migrations", "Production checklist"],
  },
];

export default function DocsPage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">Documentation</div>
      <h1 className="text-4xl font-medium">Get up and running.</h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Everything you need to configure CareerCraft AI and start automating your job search.
      </p>

      <div className="mt-12 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
        Full documentation is coming soon. In the meantime, check the{" "}
        <a
          href="https://github.com"
          className="font-medium underline hover:no-underline"
          target="_blank"
          rel="noreferrer"
        >
          GitHub repo
        </a>{" "}
        README for setup instructions.
      </div>

      <div className="mt-12 grid gap-6 sm:grid-cols-2">
        {SECTIONS.map((section) => (
          <div key={section.title} className="rounded-3xl border border-border bg-card/60 p-6">
            <h2 className="text-base font-semibold">{section.title}</h2>
            <ul className="mt-4 space-y-2">
              {section.items.map((item) => (
                <li key={item} className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span className="h-1 w-1 rounded-full bg-muted-foreground/40" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="mt-12">
        <Link href="/contact" className="text-sm text-primary hover:underline">
          Can&apos;t find what you&apos;re looking for? Contact us →
        </Link>
      </div>
    </div>
  );
}
