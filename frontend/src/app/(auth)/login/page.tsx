"use client";

import React, { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { SignInPage, type AuthMode, type Testimonial } from "@/components/ui/sign-in";

const GMAIL_SCOPES = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/gmail.send",
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/drive.readonly",
].join(" ");

const TESTIMONIALS: Testimonial[] = [
  {
    avatarSrc: "https://randomuser.me/api/portraits/women/57.jpg",
    name: "Sarah Chen",
    handle: "@sarahdigital",
    text: "Tailored applications in minutes. Landed three interviews the first week.",
  },
  {
    avatarSrc: "https://randomuser.me/api/portraits/men/64.jpg",
    name: "Marcus Johnson",
    handle: "@marcustech",
    text: "The agent rewrote my resume per role. Match scores jumped from 60 to 90.",
  },
  {
    avatarSrc: "https://randomuser.me/api/portraits/men/32.jpg",
    name: "David Martinez",
    handle: "@davidcreates",
    text: "Follow-up emails on autopilot. CareerCraft saved me hours every day.",
  },
];

const HERO_IMAGE =
  "https://images.unsplash.com/photo-1642615835477-d303d7dc9ee9?w=2160&q=80";

function useSupabase() {
  const ref = React.useRef<ReturnType<typeof createClient>>();
  if (!ref.current && typeof window !== "undefined") {
    ref.current = createClient();
  }
  return ref.current!;
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const supabase = useSupabase();
  const [mode, setMode] = useState<AuthMode>("sign-in");
  const [error, setError] = useState<string | null>(searchParams.get("error"));
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const nextPath = searchParams.get("redirect_url") ?? "/dashboard";

  const oauthSignIn = async (
    provider: "google" | "linkedin_oidc" | "github",
    scopes?: string,
  ) => {
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`,
        scopes,
        queryParams:
          provider === "google" ? { access_type: "offline", prompt: "consent" } : undefined,
      },
    });
    if (error) {
      setError(error.message);
      setLoading(false);
    }
    // success: browser redirects to provider
  };

  const handlePasswordSubmit = async ({
    email,
    password,
  }: {
    email: string;
    password: string;
  }) => {
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      if (mode === "sign-up") {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`,
          },
        });
        if (error) throw error;
        setInfo("Check your email to confirm your account.");
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push(nextPath);
        router.refresh();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const handleMagicLink = async (email: string) => {
    setError(null);
    setInfo(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`,
      },
    });
    if (error) setError(error.message);
    else setInfo("Magic link sent. Check your inbox.");
    setLoading(false);
  };

  const handleResetPassword = async () => {
    const email = window.prompt("Enter your email to receive a reset link:");
    if (!email) return;
    setError(null);
    setInfo(null);
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/callback?next=/settings/account`,
    });
    if (error) setError(error.message);
    else setInfo("Password reset link sent.");
  };

  return (
    <SignInPage
      mode={mode}
      onModeSwitch={setMode}
      testimonials={TESTIMONIALS}
      heroImageSrc={HERO_IMAGE}
      onPasswordSubmit={handlePasswordSubmit}
      onMagicLink={handleMagicLink}
      onGoogleSignIn={() => oauthSignIn("google", GMAIL_SCOPES)}
      onLinkedInSignIn={() => oauthSignIn("linkedin_oidc", "openid profile email")}
      onGithubSignIn={() => oauthSignIn("github", "read:user user:email")}
      onResetPassword={handleResetPassword}
      errorMessage={error}
      infoMessage={info}
      loading={loading}
    />
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    }>
      <LoginContent />
    </Suspense>
  );
}
