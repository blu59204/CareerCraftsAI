"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Briefcase,
  Bot,
  Mail,
  Settings,
  Sparkles,
  Search,
  Linkedin,
  MessageSquare,
  Users,
} from "lucide-react";

const ITEMS = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/resume", icon: FileText, label: "Resume" },
  { href: "/jobs", icon: Search, label: "Jobs" },
  { href: "/applications", icon: Briefcase, label: "Applications" },
  { href: "/agents", icon: Bot, label: "Agents" },
  { href: "/email", icon: Mail, label: "Email" },
  { href: "/linkedin", icon: Linkedin, label: "LinkedIn" },
  { href: "/leads", icon: Users, label: "Leads" },
  { href: "/interview-prep", icon: MessageSquare, label: "Interview Prep" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function AppSidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden h-screen w-64 shrink-0 border-r border-border bg-card/40 px-4 py-6 backdrop-blur md:flex md:flex-col">
      <Link href="/" prefetch className="mb-8 flex items-center gap-2 px-2 text-base font-semibold">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" />
        </span>
        CareerCraft AI
      </Link>
      <nav className="flex-1 space-y-1">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              prefetch
              className={`flex items-center gap-3 rounded-2xl px-3 py-2 text-sm transition-all duration-150 ${
                active
                  ? "bg-primary/15 text-foreground font-medium"
                  : "text-muted-foreground hover:bg-card hover:text-foreground active:scale-[0.98]"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
