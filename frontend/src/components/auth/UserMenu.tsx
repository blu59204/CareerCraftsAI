"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, Settings, User as UserIcon } from "lucide-react";
import { createClient } from "@/lib/supabase/client";

export function UserMenu() {
  const router = useRouter();
  const supabase = createClient();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);

  useEffect(() => {
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
  }, [supabase]);

  const initials = (email ?? "?").slice(0, 1).toUpperCase();

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  };

  if (!email) return null;

  return (
    <div className="relative">
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
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-11 z-50 w-56 overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
            <div className="border-b border-border px-4 py-3 text-sm">
              <p className="truncate text-muted-foreground">{email}</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                router.push("/settings/account");
              }}
              className="flex w-full items-center gap-2 px-4 py-2 text-sm hover:bg-secondary"
            >
              <UserIcon className="h-4 w-4" /> Account
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                router.push("/settings/models");
              }}
              className="flex w-full items-center gap-2 px-4 py-2 text-sm hover:bg-secondary"
            >
              <Settings className="h-4 w-4" /> Settings
            </button>
            <button
              type="button"
              onClick={handleSignOut}
              className="flex w-full items-center gap-2 border-t border-border px-4 py-2 text-sm text-danger hover:bg-secondary"
            >
              <LogOut className="h-4 w-4" /> Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}
