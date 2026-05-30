"use client";

import React, { useState, Suspense } from "react";
import { useAuth, useSignIn, useSignUp } from "@clerk/nextjs";
import type { SignInFutureResource, SignUpFutureResource } from "@clerk/shared/types";
import { useRouter, useSearchParams } from "next/navigation";
import {
  SignInPage,
  type AuthMode,
  type AuthPasswordSubmitData,
  type AuthResetPasswordData,
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

type OAuthStrategy = "oauth_google" | "oauth_linkedin_oidc" | "oauth_github";
type FinalizableAuthResource = SignInFutureResource | SignUpFutureResource;
type PendingVerification =
  | { kind: "signup-email"; email: string }
  | { kind: "signin-email"; email: string }
  | { kind: "reset-password"; email: string };

function getAuthErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  const clerkError = error as {
    longMessage?: string;
    message?: string;
    errors?: Array<{ longMessage?: string; message?: string }>;
  };
  return (
    clerkError.longMessage ??
    clerkError.message ??
    clerkError.errors?.[0]?.longMessage ??
    clerkError.errors?.[0]?.message ??
    "Authentication failed"
  );
}

function splitName(fullName: string) {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  return {
    firstName: parts[0] ?? undefined,
    lastName: parts.slice(1).join(" ") || undefined,
  };
}

function safeRedirectPath(path: string | null, fallback = "/dashboard") {
  if (!path || !path.startsWith("/") || path.startsWith("//")) return fallback;
  return path;
}

async function withTimeout<T>(promise: Promise<T>, message: string, ms = 20_000) {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timeoutId = setTimeout(() => reject(new Error(message)), ms);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLoaded: authLoaded, isSignedIn } = useAuth();
  const { signIn } = useSignIn();
  const { signUp } = useSignUp();
  const [mode, setMode] = useState<AuthMode>(
    searchParams.get("mode") === "sign-up" ? "sign-up" : "sign-in"
  );
  const [error, setError] = useState<string | null>(searchParams.get("error"));
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pendingVerification, setPendingVerification] = useState<PendingVerification | null>(null);
  const authInFlightRef = React.useRef(false);
  const resetPasswordRef = React.useRef<string | null>(null);

  const nextPath = safeRedirectPath(searchParams.get("redirect_url"));
  const onboardingPath = "/onboarding";

  React.useEffect(() => {
    if (authLoaded && isSignedIn) {
      router.replace(nextPath);
    }
  }, [authLoaded, isSignedIn, nextPath, router]);

  React.useEffect(() => {
    const sensitiveKeys = ["email", "password"];
    if (!sensitiveKeys.some((key) => searchParams.has(key))) return;

    const cleaned = new URLSearchParams(searchParams.toString());
    sensitiveKeys.forEach((key) => cleaned.delete(key));
    const query = cleaned.toString();
    router.replace(query ? `/login?${query}` : "/login");
  }, [router, searchParams]);

  const finalizeAuth = async (authResource: FinalizableAuthResource, destination: string) => {
    if (!authResource.createdSessionId) throw new Error("No session was created.");
    const { error: finalizeError } = await withTimeout(
      authResource.finalize(),
      "Clerk session took too long to activate. Try again.",
    );
    if (finalizeError) throw finalizeError;
    window.location.assign(destination);
  };

  const oauthSignIn = async (strategy: OAuthStrategy) => {
    if (authInFlightRef.current) return;
    authInFlightRef.current = true;
    setError(null);
    setLoading(true);
    const redirectPath = mode === "sign-up" ? onboardingPath : nextPath;
    try {
      if (mode === "sign-up") {
        if (!signUp) throw new Error("Clerk is still loading. Try again.");
        const { error: signUpError } = await withTimeout(
          signUp.sso({
            strategy,
            redirectUrl: redirectPath,
            redirectCallbackUrl: "/sso-callback",
          }),
          "Clerk OAuth took too long. Enable this provider in Clerk Dashboard and allow http://localhost:3000/sso-callback.",
        );
        if (signUpError) throw signUpError;
        if (signUp.status === "complete") {
          await finalizeAuth(signUp, redirectPath);
          return;
        }
        throw new Error(
          `Clerk did not redirect. Signup status: ${signUp.status}. Enable this provider in Clerk Dashboard and allow http://localhost:3000/sso-callback.`,
        );
      } else {
        if (!signIn) throw new Error("Clerk is still loading. Try again.");
        const { error: signInError } = await withTimeout(
          signIn.sso({
            strategy,
            redirectUrl: redirectPath,
            redirectCallbackUrl: "/sso-callback",
          }),
          "Clerk OAuth took too long. Enable this provider in Clerk Dashboard and allow http://localhost:3000/sso-callback.",
        );
        if (signInError) throw signInError;
        if (signIn.status === "complete") {
          await finalizeAuth(signIn, redirectPath);
          return;
        }
        throw new Error(
          `Clerk did not redirect. Signin status: ${signIn.status}. Enable this provider in Clerk Dashboard and allow http://localhost:3000/sso-callback.`,
        );
      }
    } catch (e) {
      setError(getAuthErrorMessage(e));
    } finally {
      authInFlightRef.current = false;
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
    if (authInFlightRef.current) return;
    authInFlightRef.current = true;
    setError(null);
    setInfo(null);
    setPendingVerification(null);
    setLoading(true);
    try {
      if (mode === "sign-up") {
        if (!signUp) throw new Error("Clerk is still loading. Try again.");
        if (!fullName || !phone) {
          throw new Error("Enter your full name and phone number.");
        }

        const { firstName, lastName } = splitName(fullName);
        const profilePayload = {
          full_name: fullName,
          name: fullName,
          phone,
          headline,
          linkedin_url: linkedinUrl,
        };

        const { error: signUpError } = await withTimeout(
          signUp.password({
            emailAddress: email,
            password,
            firstName,
            lastName,
            unsafeMetadata: profilePayload,
          }),
          "Signup took too long. Check Clerk configuration and try again.",
        );
        if (signUpError) throw signUpError;

        if (signUp.status === "complete") {
          await finalizeAuth(signUp, onboardingPath);
          return;
        }

        if (signUp.unverifiedFields.includes("email_address")) {
          const { error: sendError } = await withTimeout(
            signUp.verifications.sendEmailCode(),
            "Email verification took too long. Try again.",
          );
          if (sendError) throw sendError;
          setPendingVerification({ kind: "signup-email", email });
          setInfo("Verification code sent. Enter it below to finish signup.");
          return;
        }

        setInfo("Check Clerk for any remaining verification step, then sign in.");
      } else {
        if (!signIn) throw new Error("Clerk is still loading. Try again.");
        const { error: signInError } = await withTimeout(
          signIn.password({ identifier: email, password }),
          "Signin took too long. Check Clerk configuration and try again.",
        );
        if (signInError) throw signInError;
        if (signIn.status !== "complete") {
          throw new Error("Additional verification is required for this account.");
        }
        await finalizeAuth(signIn, nextPath);
      }
    } catch (e) {
      setError(getAuthErrorMessage(e));
    } finally {
      authInFlightRef.current = false;
      setLoading(false);
    }
  };

  const handleMagicLink = async (email: string) => {
    if (authInFlightRef.current) return;
    authInFlightRef.current = true;
    setError(null);
    setInfo(null);
    setPendingVerification(null);
    setLoading(true);
    try {
      if (!signIn) throw new Error("Clerk is still loading. Try again.");
      const { error: sendError } = await withTimeout(
        signIn.emailCode.sendCode({ emailAddress: email }),
        "Email code took too long. Try again.",
      );
      if (sendError) throw sendError;
      setPendingVerification({ kind: "signin-email", email });
      setInfo("Email code sent. Enter it below to continue.");
    } catch (e) {
      setError(getAuthErrorMessage(e));
    } finally {
      authInFlightRef.current = false;
      setLoading(false);
    }
  };

  const handleVerificationSubmit = async (code: string) => {
    if (authInFlightRef.current || !pendingVerification) return;
    authInFlightRef.current = true;
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      if (pendingVerification.kind === "signup-email") {
        if (!signUp) throw new Error("Clerk is still loading. Try again.");
        const { error: verifyError } = await withTimeout(
          signUp.verifications.verifyEmailCode({ code }),
          "Email verification took too long. Try again.",
        );
        if (verifyError) throw verifyError;
        if ((signUp.status as string) === "complete") {
          await finalizeAuth(signUp, onboardingPath);
          return;
        }
        setInfo("Check Clerk for any remaining verification step, then sign in.");
        return;
      }

      if (!signIn) throw new Error("Clerk is still loading. Try again.");
      if (pendingVerification.kind === "reset-password") {
        const newPassword = resetPasswordRef.current;
        if (!newPassword) throw new Error("New password was not found. Start password reset again.");
        const { error: verifyError } = await withTimeout(
          signIn.resetPasswordEmailCode.verifyCode({ code }),
          "Password reset verification took too long. Try again.",
        );
        if (verifyError) throw verifyError;
        const { error: submitError } = await withTimeout(
          signIn.resetPasswordEmailCode.submitPassword({
            password: newPassword,
            signOutOfOtherSessions: true,
          }),
          "Password reset took too long. Try again.",
        );
        if (submitError) throw submitError;
        resetPasswordRef.current = null;
        if (signIn.status === "complete") {
          await finalizeAuth(signIn, "/settings/account");
          return;
        }
        setInfo("Password reset needs one more verification step in Clerk.");
        return;
      }

      const { error: verifyError } = await withTimeout(
        signIn.emailCode.verifyCode({ code }),
        "Email code verification took too long. Try again.",
      );
      if (verifyError) throw verifyError;
      if (signIn.status !== "complete") {
        throw new Error("Additional verification is required for this account.");
      }
      await finalizeAuth(signIn, nextPath);
    } catch (e) {
      setError(getAuthErrorMessage(e));
    } finally {
      authInFlightRef.current = false;
      setLoading(false);
    }
  };

  const handleVerificationCancel = () => {
    if (loading) return;
    authInFlightRef.current = false;
    resetPasswordRef.current = null;
    setPendingVerification(null);
    setError(null);
    setInfo(null);
  };

  const handleResetPassword = async ({ email, password }: AuthResetPasswordData) => {
    if (authInFlightRef.current) return;
    authInFlightRef.current = true;
    setError(null);
    setInfo(null);
    setPendingVerification(null);
    resetPasswordRef.current = null;
    setLoading(true);
    try {
      if (!signIn) throw new Error("Clerk is still loading. Try again.");
      const { error: createError } = await withTimeout(
        signIn.create({ identifier: email }),
        "Password reset took too long. Try again.",
      );
      if (createError) throw createError;
      const { error: sendError } = await withTimeout(
        signIn.resetPasswordEmailCode.sendCode(),
        "Password reset email took too long. Try again.",
      );
      if (sendError) throw sendError;
      resetPasswordRef.current = password;
      setPendingVerification({ kind: "reset-password", email });
      setInfo("Password reset code sent. Enter it below to finish.");
    } catch (e) {
      setError(getAuthErrorMessage(e));
    } finally {
      authInFlightRef.current = false;
      setLoading(false);
    }
  };

  if (authLoaded && isSignedIn) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <SignInPage
      mode={mode}
      onModeSwitch={setMode}
      testimonials={TESTIMONIALS}
      heroImageSrc={HERO_IMAGE}
      onPasswordSubmit={handlePasswordSubmit}
      onMagicLink={handleMagicLink}
      onGoogleSignIn={() => oauthSignIn("oauth_google")}
      onLinkedInSignIn={() => oauthSignIn("oauth_linkedin_oidc")}
      onGithubSignIn={() => oauthSignIn("oauth_github")}
      onResetPassword={handleResetPassword}
      verification={
        pendingVerification
          ? {
              email: pendingVerification.email,
              title: "Check your email",
              description: `Enter the code sent to ${pendingVerification.email}.`,
            }
          : null
      }
      onVerificationSubmit={handleVerificationSubmit}
      onVerificationCancel={handleVerificationCancel}
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
