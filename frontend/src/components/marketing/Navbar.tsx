"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useAuth } from "@clerk/nextjs";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

const UserMenu = dynamic(
  () => import("@/components/auth/UserMenu").then((m) => ({ default: m.UserMenu })),
  { ssr: false },
);

const NAV = [
  { href: "/#features", label: "Features" },
  { href: "/#how", label: "How it Works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/#demo", label: "Demo" },
];

export function MarketingNavbar() {
  const { isLoaded, isSignedIn } = useAuth();
  const signedIn = isLoaded && isSignedIn;

  return (
    <header className="fixed left-0 right-0 top-4 z-40 px-4">
      <div className="font-chrome mx-auto flex h-12 max-w-5xl items-center justify-between rounded-full border border-white/55 bg-white/[0.045] px-3 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.55),0_18px_54px_rgba(0,0,0,0.07)] backdrop-blur-[32px] backdrop-saturate-[210%] dark:border-white/18 dark:bg-black/[0.16] dark:text-[#E1E0CC] sm:px-4">
        <Link href="/" className="flex items-center gap-2 whitespace-nowrap text-sm font-semibold tracking-[-0.01em]">
          <span className="h-2 w-2 rounded-full bg-primary" />
          <span className="font-semibold sm:hidden">CareerCraft</span>
          <span className="hidden font-semibold sm:inline">CareerCraft AI</span>
        </Link>
        <nav className="hidden items-center gap-1 rounded-full border border-white/45 bg-white/[0.075] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.45)] backdrop-blur-[26px] backdrop-saturate-[200%] md:flex dark:border-white/12 dark:bg-white/[0.07]">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="rounded-full px-4 py-1.5 text-[13px] font-semibold text-foreground/70 transition hover:bg-white/[0.18] hover:text-foreground dark:text-[#E1E0CC]/72 dark:hover:bg-white/10 dark:hover:text-[#E1E0CC]"
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          {!signedIn && (
            <>
              <Link
                href="/login"
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                Log in
              </Link>
              <Link
                href="/register"
              className="inline-flex h-9 items-center rounded-full bg-foreground px-4 text-sm font-semibold text-background transition hover:scale-[1.02]"
              >
                Get Started
              </Link>
            </>
          )}
          {signedIn && (
            <>
              <Link
                href="/dashboard"
                className="inline-flex h-9 items-center rounded-full bg-foreground px-4 text-sm font-semibold text-background transition hover:scale-[1.02]"
              >
                Dashboard
              </Link>
              <UserMenu />
            </>
          )}
        </div>
      </div>
    </header>
  );
}
