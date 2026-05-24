import Link from "next/link";
import { VideoBackground } from "@/components/ui/VideoBackground";

const COLUMNS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Product",
    links: [
      { href: "/#features", label: "Features" },
      { href: "/pricing", label: "Pricing" },
      { href: "/#how", label: "How it Works" },
    ],
  },
  {
    title: "Agents",
    links: [
      { href: "/agents?focus=resume", label: "Resume Agent" },
      { href: "/agents?focus=job", label: "Job Search Agent" },
      { href: "/agents?focus=email", label: "Email Agent" },
      { href: "/agents?focus=followup", label: "Follow-up Agent" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/privacy", label: "Privacy" },
      { href: "/terms", label: "Terms" },
    ],
  },
  {
    title: "Support",
    links: [
      { href: "/docs", label: "Docs" },
      { href: "/contact", label: "Contact" },
      { href: "/status", label: "Status" },
    ],
  },
];

export function MarketingFooter() {
  return (
    <footer className="relative isolate mt-32 overflow-hidden rounded-t-[3rem] border-t border-border">
      <VideoBackground src="/videos/footer.mp4" poster="/videos/footer-poster.jpg" overlayClassName="bg-background/85" />
      <div className="relative mx-auto max-w-7xl px-6 py-20">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-5">
          <div className="col-span-2">
            <div className="text-2xl font-semibold">CareerCraft AI</div>
            <p className="mt-3 max-w-xs text-sm text-muted-foreground">
              The AI job-search copilot for students and freshers. Tailor resumes, match jobs, follow up — automatically.
            </p>
          </div>
          {COLUMNS.map((c) => (
            <div key={c.title}>
              <div className="text-sm font-medium">{c.title}</div>
              <ul className="mt-4 space-y-2">
                {c.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} className="text-sm text-muted-foreground hover:text-foreground">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-14 flex items-center justify-between border-t border-border/60 pt-6 text-xs text-muted-foreground">
          <span>© {new Date().getFullYear()} CareerCraft AI</span>
          <span>Built with care.</span>
        </div>
      </div>
    </footer>
  );
}
