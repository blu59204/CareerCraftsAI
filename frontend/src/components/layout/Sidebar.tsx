"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/resume/optimize", label: "Resume" },
  { href: "/jobs/search", label: "Job Search" },
  { href: "/applications", label: "Applications" },
  { href: "/settings/models", label: "Settings" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 border-r bg-slate-50 min-h-screen p-4 space-y-1 shrink-0">
      <div className="font-bold text-lg mb-6 px-2">JobAgent AI</div>
      {NAV.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={cn(
            "block px-3 py-2 rounded-md text-sm transition-colors",
            path.startsWith(item.href)
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:bg-slate-200",
          )}
        >
          {item.label}
        </Link>
      ))}
    </aside>
  );
}
