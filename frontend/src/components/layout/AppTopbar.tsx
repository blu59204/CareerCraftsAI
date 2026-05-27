"use client";

import { useState, useRef, useEffect } from "react";
import dynamic from "next/dynamic";
import { Bell, Search, CheckCircle, Briefcase, Mail, Calendar } from "lucide-react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { cn } from "@/lib/utils";

const UserMenu = dynamic(
  () => import("@/components/auth/UserMenu").then((m) => ({ default: m.UserMenu })),
  { ssr: false },
);

const NOTIFICATIONS = [
  {
    id: "1",
    icon: Briefcase,
    title: "Job Agent found 3 new matches",
    time: "2m ago",
    read: false,
  },
  {
    id: "2",
    icon: Mail,
    title: "Follow-up email draft ready for review",
    time: "1h ago",
    read: false,
  },
  {
    id: "3",
    icon: Calendar,
    title: "Interview scheduled — BetaCorp tomorrow",
    time: "3h ago",
    read: true,
  },
  {
    id: "4",
    icon: CheckCircle,
    title: "Resume optimization complete",
    time: "Yesterday",
    read: true,
  },
];

export function AppTopbar() {
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState(NOTIFICATIONS);
  const notifRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!notifOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (!notifRef.current?.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [notifOpen]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const markAllRead = () =>
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-border bg-background/70 px-6 backdrop-blur">
      <div className="flex flex-1 items-center gap-2 rounded-full border border-border bg-card/40 px-4 py-2 max-w-md">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input
          placeholder="Search jobs, applications, agents…"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>

      {/* Notifications */}
      <div ref={notifRef} className="relative">
        <button
          type="button"
          aria-label="Notifications"
          onClick={() => setNotifOpen((v) => !v)}
          className="relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card/60 text-foreground hover:bg-card"
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute right-1.5 top-1.5 flex h-2 w-2 items-center justify-center rounded-full bg-primary">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
            </span>
          )}
        </button>

        {notifOpen && (
          <div className="absolute right-0 top-11 z-50 w-80 overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <span className="text-sm font-semibold">Notifications</span>
              {unreadCount > 0 && (
                <button
                  onClick={markAllRead}
                  className="text-xs text-primary hover:underline"
                >
                  Mark all read
                </button>
              )}
            </div>
            <div className="max-h-72 overflow-y-auto">
              {notifications.map((n) => {
                const Icon = n.icon;
                return (
                  <div
                    key={n.id}
                    onClick={() =>
                      setNotifications((prev) =>
                        prev.map((x) => (x.id === n.id ? { ...x, read: true } : x))
                      )
                    }
                    className={cn(
                      "flex cursor-pointer items-start gap-3 px-4 py-3 transition-colors hover:bg-secondary",
                      !n.read && "bg-primary/5"
                    )}
                  >
                    <div
                      className={cn(
                        "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                        n.read ? "bg-muted" : "bg-primary/10"
                      )}
                    >
                      <Icon className={cn("h-3.5 w-3.5", n.read ? "text-muted-foreground" : "text-primary")} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className={cn("text-xs leading-snug", !n.read && "font-medium")}>
                        {n.title}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">{n.time}</p>
                    </div>
                    {!n.read && (
                      <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
                    )}
                  </div>
                );
              })}
              {notifications.length === 0 && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground">
                  No notifications
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <ThemeToggle />
      <UserMenu />
    </header>
  );
}
