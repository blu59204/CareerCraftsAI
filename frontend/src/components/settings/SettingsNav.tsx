"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrainCircuit, Cable, UserRound } from "lucide-react";

const sections = [
  { href: "/settings/account", label: "Profile", icon: UserRound },
  { href: "/settings/integrations", label: "Integrations", icon: Cable },
  { href: "/settings/models", label: "AI models & keys", icon: BrainCircuit },
];

export function SettingsNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Settings sections" className="flex w-full gap-1 overflow-x-auto rounded-2xl border border-border bg-card/50 p-1">
      {sections.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`inline-flex min-w-fit items-center gap-2 rounded-xl px-3 py-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:px-4 ${active ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:bg-background/60 hover:text-foreground"}`}
          >
            <Icon aria-hidden className="h-4 w-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
