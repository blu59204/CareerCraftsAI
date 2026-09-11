"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, Settings, User as UserIcon } from "lucide-react";
import { useClerk, useUser } from "@clerk/nextjs";
import { apiClient } from "@/lib/api";

interface UserProfile {
  email: string;
  full_name: string | null;
  avatar_url: string | null;
}

export function UserMenu() {
  const router = useRouter();
  const { isLoaded, isSignedIn, user } = useUser();
  const { signOut } = useClerk();
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    if (!isLoaded) return;
    if (!isSignedIn) {
      setProfile(null);
      return;
    }

    // Backend profile is authoritative; the Clerk user is the fallback while it
    // loads (or when the backend is unreachable).
    apiClient
      .get<UserProfile>("/users/me")
      .then(({ data }) => {
        if (!cancelled) setProfile(data);
      })
      .catch(() => {
        if (cancelled) return;
        setProfile({
          email: user?.primaryEmailAddress?.emailAddress ?? "",
          full_name: user?.fullName ?? null,
          avatar_url: user?.imageUrl ?? null,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [isLoaded, isSignedIn, user]);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const email = profile?.email || user?.primaryEmailAddress?.emailAddress || null;
  const displayName = profile?.full_name || user?.fullName || email;
  const avatarUrl = profile?.avatar_url ?? user?.imageUrl ?? null;
  const initials = (displayName ?? "?")
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const handleSignOut = async () => {
    setOpen(false);
    await signOut();
    router.push("/");
    router.refresh();
  };

  if (!isLoaded || !isSignedIn || !email) return null;

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Account menu"
        className="inline-flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border border-border bg-primary/10 text-sm font-medium text-primary shadow-sm transition hover:bg-primary/15"
      >
        {avatarUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatarUrl} alt={email} className="h-full w-full object-cover" />
        ) : (
          initials
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-[100] w-64 overflow-hidden rounded-2xl border border-border bg-card/95 shadow-2xl backdrop-blur-xl">
          <div className="border-b border-border px-4 py-3 text-sm">
            <p className="mb-1 truncate font-medium text-foreground">{displayName}</p>
            <p className="truncate text-muted-foreground">{email}</p>
          </div>
          <Link
            href="/settings/account"
            onClick={() => setOpen(false)}
            className="flex w-full items-center gap-2 px-4 py-2 text-sm hover:bg-secondary"
          >
            <UserIcon className="h-4 w-4" /> Account
          </Link>
          <Link
            href="/settings/models"
            onClick={() => setOpen(false)}
            className="flex w-full items-center gap-2 px-4 py-2 text-sm hover:bg-secondary"
          >
            <Settings className="h-4 w-4" /> Settings
          </Link>
          <button
            type="button"
            onClick={handleSignOut}
            className="flex w-full items-center gap-2 border-t border-border px-4 py-3 text-sm font-medium text-danger hover:bg-danger/10"
          >
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      )}
    </div>
  );
}
