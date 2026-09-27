"use client";

import { useState, useRef, useEffect } from "react";
import dynamic from "next/dynamic";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, Search, CheckCircle, Briefcase, Mail, Menu, X } from "lucide-react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";

const UserMenu = dynamic(
  () => import("@/components/auth/UserMenu").then((m) => ({ default: m.UserMenu })),
  { ssr: false },
);

type Notification = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  read: boolean;
  created_at: string;
};

type NotificationListResponse = {
  notifications: Notification[];
  unread_count: number;
};

const TYPE_ICON: Record<string, typeof Bell> = {
  job_matches: Briefcase,
  followup_ready: Mail,
};

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  return `${days}d ago`;
}

export function AppTopbar({ onMenuClick }: { onMenuClick?: () => void }) {
  const [notifOpen, setNotifOpen] = useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const { data } = useQuery<NotificationListResponse>({
    queryKey: ["notifications"],
    queryFn: async () => (await apiClient.get("/notifications")).data,
    refetchInterval: 30_000,
  });
  const notifications = data?.notifications ?? [];
  const unreadCount = data?.unread_count ?? 0;

  const markRead = useMutation({
    mutationFn: async (id: string) => apiClient.patch(`/notifications/${id}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const markAllRead = useMutation({
    mutationFn: async () => apiClient.post("/notifications/read-all"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

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

  return (
    <header className="glass-panel sticky top-4 z-30 mx-4 mt-4 flex h-16 items-center gap-2 overflow-visible rounded-full px-4 sm:gap-4 md:mx-6">
      {!mobileSearchOpen && (
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="shrink-0 rounded-full p-2 text-muted-foreground hover:bg-white/[0.12] hover:text-foreground md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
      )}

      {/* Desktop/tablet: full search pill. Hidden on mobile in favor of an icon
          button — at 390px a flex-1 input with content-sized min-width pushed
          the notification bell past the pill's rounded border. */}
      <div className="hidden min-w-0 max-w-md flex-1 items-center gap-2 rounded-full border border-white/45 bg-white/[0.10] px-4 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.45)] backdrop-blur-[20px] dark:border-white/10 dark:bg-black/[0.12] sm:flex">
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
        <input
          placeholder="Search jobs, applications, agents…"
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>

      {/* Mobile: collapsed search icon that expands into an inline input. */}
      {mobileSearchOpen ? (
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-full border border-white/45 bg-white/[0.10] px-4 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.45)] backdrop-blur-[20px] dark:border-white/10 dark:bg-black/[0.12] sm:hidden">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            autoFocus
            placeholder="Search…"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <button
            type="button"
            onClick={() => setMobileSearchOpen(false)}
            aria-label="Close search"
            className="shrink-0 rounded-full p-1 text-muted-foreground hover:bg-white/[0.12] hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setMobileSearchOpen(true)}
          aria-label="Search"
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/45 bg-white/[0.10] text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.40)] backdrop-blur-[18px] hover:bg-white/[0.16] dark:border-white/10 dark:bg-black/[0.12] dark:hover:bg-white/[0.08] sm:hidden"
        >
          <Search className="h-4 w-4" />
        </button>
      )}

      <span className="hidden shrink-0 items-center gap-1.5 rounded-full border border-white/40 bg-white/[0.10] px-3 py-1.5 text-xs font-medium text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.35)] backdrop-blur-[18px] sm:inline-flex dark:border-white/10 dark:bg-black/[0.12]">
        <span className="signal-dot h-1.5 w-1.5 rounded-full bg-success" />
        Agents online
      </span>

      {!mobileSearchOpen && (
      <div className="ml-auto flex shrink-0 items-center gap-3">
        {/* Notifications */}
        <div ref={notifRef} className="relative">
          <button
            type="button"
            aria-label="Notifications"
            onClick={() => setNotifOpen((v) => !v)}
            className="relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/45 bg-white/[0.10] text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.40)] backdrop-blur-[18px] hover:bg-white/[0.16] dark:border-white/10 dark:bg-black/[0.12] dark:hover:bg-white/[0.08]"
          >
            <Bell className="h-4 w-4" />
            {unreadCount > 0 && (
              <span className="absolute right-1.5 top-1.5 flex h-2 w-2 items-center justify-center rounded-full bg-primary">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
              </span>
            )}
          </button>

          {notifOpen && (
            <div className="glass-panel-strong absolute right-0 top-11 z-50 w-80 overflow-hidden rounded-2xl">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <span className="text-sm font-semibold">Notifications</span>
                {unreadCount > 0 && (
                  <button
                    onClick={() => markAllRead.mutate()}
                    className="text-xs text-primary hover:underline"
                  >
                    Mark all read
                  </button>
                )}
              </div>
              <div className="max-h-72 overflow-y-auto">
                {notifications.map((n) => {
                  const Icon = TYPE_ICON[n.type] ?? CheckCircle;
                  return (
                    <a
                      key={n.id}
                      href={n.link ?? undefined}
                      onClick={() => {
                        if (!n.read) markRead.mutate(n.id);
                      }}
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
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {relativeTime(n.created_at)}
                        </p>
                      </div>
                      {!n.read && (
                        <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
                      )}
                    </a>
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
      </div>
      )}
    </header>
  );
}
