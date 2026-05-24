"use client";

import { UserButton } from "@clerk/nextjs";
import { Bell, Search } from "lucide-react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

export function AppTopbar() {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-border bg-background/70 px-6 backdrop-blur">
      <div className="flex flex-1 items-center gap-2 rounded-full border border-border bg-card/40 px-4 py-2 max-w-md">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input
          placeholder="Search jobs, applications, agents…"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      <button
        type="button"
        aria-label="Notifications"
        className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card/60 text-foreground hover:bg-card"
      >
        <Bell className="h-4 w-4" />
      </button>
      <ThemeToggle />
      <UserButton afterSignOutUrl="/" />
    </header>
  );
}
