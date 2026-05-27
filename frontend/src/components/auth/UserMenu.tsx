"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, Settings, User as UserIcon } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import type { SupabaseClient } from "@supabase/supabase-js";

export function UserMenu() {
  const router = useRouter();
  const supabaseRef = useRef<SupabaseClient | null>(null);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const supabase = createClient();
    supabaseRef.current = supabase;
    let mounted = true;
    supabase.auth.getUser().then(({ data }) => {
      if (!mounted) return;
      setEmail(data.user?.email ?? null);
      setAvatarUrl(
        (data.user?.user_metadata?.avatar_url as string | undefined) ?? null,
      );
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) => {
      setEmail(session?.user.email ?? null);
      setAvatarUrl((session?.user.user_metadata?.avatar_url as string | undefined) ?? null);
    });
    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, []);

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

  const initials = (email ?? "?").slice(0, 1).toUpperCase();

  const handleSignOut = async () => {
    setOpen(false);
    await supabaseRef.current?.auth.signOut();
    router.push("/");
    router.refresh();
  };

  if (!email) return null;

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Account menu"
        className="inline-flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border border-border bg-primary/10 text-sm font-medium text-primary"
      >
        {avatarUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatarUrl} alt={email} className="h-full w-full object-cover" />
        ) : (
          initials
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-11 z-50 w-56 overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
          <div className="border-b border-border px-4 py-3 text-sm">
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
            className="flex w-full items-center gap-2 border-t border-border px-4 py-2 text-sm text-danger hover:bg-secondary"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
