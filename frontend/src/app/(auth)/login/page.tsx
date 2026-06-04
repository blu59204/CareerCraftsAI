"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import {
  SignInPage,
  type AuthMode,
  type AuthPasswordSubmitData,
  type Testimonial,
} from "@/components/ui/sign-in";

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

export default function LoginPage() {
  const router = useRouter();
  const supabase = createClient();
  const [mode, setMode] = useState<AuthMode>("sign-in");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setErrorMessage(null);

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        // Gmail + Drive scopes power the Email agent. access_type=offline +
        // prompt=consent make Google return a refresh token and provider_token.
        scopes: [
          "https://www.googleapis.com/auth/gmail.send",
          "https://www.googleapis.com/auth/gmail.readonly",
          // drive.file = least-privilege write (only files the app creates).
          "https://www.googleapis.com/auth/drive.file",
        ].join(" "),
        queryParams: {
          access_type: "offline",
          prompt: "consent",
        },
      },
    });

    if (error) {
      setErrorMessage(error.message);
      setLoading(false);
    }
  };

  const handleGithubSignIn = async () => {
    setLoading(true);
    setErrorMessage(null);

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "github",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    if (error) {
      setErrorMessage(error.message);
      setLoading(false);
    }
  };

  const handleLinkedInSignIn = async () => {
    setLoading(true);
    setErrorMessage(null);

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "linkedin_oidc",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    if (error) {
      setErrorMessage(error.message);
      setLoading(false);
    }
  };

  const handlePasswordSubmit = async ({
    email,
    password,
    fullName,
    phone,
    headline,
    linkedinUrl,
  }: AuthPasswordSubmitData) => {
    setLoading(true);
    setErrorMessage(null);

    if (mode === "sign-in") {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        setErrorMessage(error.message);
        setLoading(false);
      } else {
        router.push("/dashboard");
      }
    } else {
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
          data: {
            full_name: fullName,
            phone,
            headline,
            linkedin_url: linkedinUrl,
          },
        },
      });

      if (error) {
        setErrorMessage(error.message);
        setLoading(false);
      }
    }
  };

  return (
    <SignInPage
      mode={mode}
      onModeSwitch={setMode}
      testimonials={TESTIMONIALS}
      heroImageSrc={HERO_IMAGE}
      onPasswordSubmit={handlePasswordSubmit}
      onMagicLink={() => {}}
      onGoogleSignIn={handleGoogleSignIn}
      onLinkedInSignIn={handleLinkedInSignIn}
      onGithubSignIn={handleGithubSignIn}
      onResetPassword={() => {}}
      verification={null}
      onVerificationSubmit={() => {}}
      onVerificationCancel={() => {}}
      errorMessage={errorMessage}
      infoMessage={null}
      loading={loading}
    />
  );
}
