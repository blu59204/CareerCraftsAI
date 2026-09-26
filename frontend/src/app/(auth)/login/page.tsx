"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
// `@clerk/nextjs/legacy` exposes the classic custom-flow hooks
// ({ isLoaded, signIn, setActive }). Nothing here renders Clerk UI.
import { useSignIn, useSignUp } from "@clerk/nextjs/legacy";
import { useAuth } from "@clerk/nextjs";
import type { OAuthStrategy } from "@clerk/nextjs/types";
import {
  SignInPage,
  type AuthMode,
  type AuthPasswordSubmitData,
  type AuthVerificationState,
} from "@/components/ui/sign-in";
import { apiClient } from "@/lib/api";

// Unsplash source URLs rot/404 over time — picsum's seeded endpoint is stable.
const HERO_IMAGE = "https://picsum.photos/seed/careercraft-login/2160/2700";

const DEFAULT_DESTINATION = "/dashboard";

/** Only ever follow same-origin paths out of `?redirect_url=`. */
function safeDestination(raw: string | null): string {
  if (!raw) return DEFAULT_DESTINATION;
  try {
    const url = new URL(raw, window.location.origin);
    if (url.origin !== window.location.origin) return DEFAULT_DESTINATION;
    const path = `${url.pathname}${url.search}`;
    if (!path.startsWith("/") || path.startsWith("//")) return DEFAULT_DESTINATION;
    if (path.startsWith("/login") || path.startsWith("/register")) return DEFAULT_DESTINATION;
    return path;
  } catch {
    return DEFAULT_DESTINATION;
  }
}

function describeError(err: unknown): string {
  const clerkErrors = (err as { errors?: { longMessage?: string; message?: string }[] })?.errors;
  const first = clerkErrors?.[0];
  return first?.longMessage || first?.message || "Something went wrong. Please try again.";
}

export default function LoginPage() {
  const router = useRouter();
  const { isLoaded: authLoaded, isSignedIn } = useAuth();
  const { isLoaded: signInLoaded, signIn, setActive: setSignInActive } = useSignIn();
  const { isLoaded: signUpLoaded, signUp, setActive: setSignUpActive } = useSignUp();

  const [mode, setMode] = useState<AuthMode>("sign-in");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [verification, setVerification] = useState<AuthVerificationState | null>(null);
  // Which flow the code field is completing — a new account, or a sign-in whose
  // only enabled first factor is an emailed code.
  const [verificationFlow, setVerificationFlow] = useState<"sign-up" | "sign-in" | "sign-in-second">("sign-up");
  const [destination, setDestination] = useState(DEFAULT_DESTINATION);

  // Read query params from the browser instead of `useSearchParams()` so this
  // page does not need a Suspense boundary during static prerendering.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mode") === "sign-up") setMode("sign-up");
    setDestination(safeDestination(params.get("redirect_url")));
    const oauthError = params.get("error");
    if (oauthError) setErrorMessage(decodeURIComponent(oauthError));
  }, []);

  // Already signed in — don't show the sign-in/sign-up form at all, send them
  // straight to the app instead of making them look at a login page they
  // can't usefully use.
  useEffect(() => {
    if (authLoaded && isSignedIn) {
      router.replace(destination);
    }
  }, [authLoaded, isSignedIn, destination, router]);

  const clerkReady = signInLoaded && signUpLoaded && !!signIn && !!signUp;

  const startOAuth = async (strategy: OAuthStrategy) => {
    if (!signIn) return;
    setLoading(true);
    setErrorMessage(null);

    try {
      // Provider scopes (Gmail/Drive for the Email agent) are configured on the
      // Google connection in the Clerk Dashboard, not passed from the client.
      await signIn.authenticateWithRedirect({
        strategy,
        redirectUrl: "/sso-callback",
        redirectUrlComplete: destination,
      });
    } catch (err) {
      setErrorMessage(describeError(err));
      setLoading(false);
    }
  };

  const handleGoogleSignIn = () => void startOAuth("oauth_google");
  const handleGithubSignIn = () => void startOAuth("oauth_github");
  const handleLinkedInSignIn = () => void startOAuth("oauth_linkedin_oidc");

  const handlePasswordSubmit = async ({
    email,
    password,
    fullName,
    phone,
    headline,
    linkedinUrl,
  }: AuthPasswordSubmitData) => {
    if (!signIn || !signUp || !setSignInActive) return;

    setLoading(true);
    setErrorMessage(null);
    setInfoMessage(null);

    if (mode === "sign-in") {
      try {
        // Which first factors exist is instance configuration, not something
        // the client can assume. Passing a password to create() when password
        // is not an enabled first factor leaves the attempt in a non-complete
        // state that surfaces as an unexplained "needs_second_factor", so ask
        // Clerk what it supports before choosing a strategy.
        const attempt = await signIn.create({ identifier: email });
        const factors = attempt.supportedFirstFactors ?? [];
        const supportsPassword = factors.some((f) => f.strategy === "password");
        const emailCodeFactor = factors.find((f) => f.strategy === "email_code");

        if (supportsPassword && password) {
          const result = await signIn.attemptFirstFactor({ strategy: "password", password });
          if (result.status === "complete") {
            await setSignInActive({ session: result.createdSessionId });
            router.push(destination);
            return;
          }

          // A correct password can still land on needs_second_factor — Clerk
          // asks for an emailed code to confirm ownership. Previously this
          // dead-ended with the raw status printed at the user, which is why
          // password sign-in appeared broken. Drive the second factor instead.
          if (result.status === "needs_second_factor") {
            const second = (result.supportedSecondFactors ?? []).find(
              (f) => f.strategy === "email_code",
            );
            if (second) {
              await signIn.prepareSecondFactor({ strategy: "email_code" });
              setVerificationFlow("sign-in-second");
              setVerification({
                email,
                title: "Confirm it's you",
                description: `We sent a confirmation code to ${email}.`,
              });
              return;
            }
          }

          setErrorMessage(
            `Additional verification is required to finish signing in (${result.status}).`,
          );
          return;
        }

        if (emailCodeFactor) {
          // Password is off for this instance — fall back to the emailed code
          // rather than dead-ending the user on a form they cannot submit.
          await signIn.prepareFirstFactor({
            strategy: "email_code",
            emailAddressId: (emailCodeFactor as { emailAddressId: string }).emailAddressId,
          });
          setVerificationFlow("sign-in");
          setVerification({
            email,
            description: `Password sign-in is turned off for this workspace. We sent a sign-in code to ${email}.`,
          });
          return;
        }

        setErrorMessage(
          "No supported sign-in method is enabled for this workspace. Try a social provider.",
        );
      } catch (err) {
        setErrorMessage(describeError(err));
      } finally {
        setLoading(false);
      }
      return;
    }

    try {
      await signUp.create({
        emailAddress: email,
        password,
        unsafeMetadata: {
          full_name: fullName,
          phone,
          headline,
          linkedin_url: linkedinUrl,
        },
      });
      await signUp.prepareEmailAddressVerification({ strategy: "email_code" });
      setVerificationFlow("sign-up");
      setVerification({ email });
      setInfoMessage(null);
    } catch (err) {
      setErrorMessage(describeError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleVerificationSubmit = async (code: string) => {
    setLoading(true);
    setErrorMessage(null);

    // The same code field now serves two flows: confirming a new account, and
    // completing a sign-in when email_code is the only enabled first factor.
    if (verificationFlow === "sign-in" || verificationFlow === "sign-in-second") {
      if (!signIn || !setSignInActive) return;
      try {
        // email_code serves as the first factor when password is disabled, and
        // as the second factor when Clerk wants ownership confirmed after a
        // correct password. Same code field, different Clerk call.
        const result =
          verificationFlow === "sign-in-second"
            ? await signIn.attemptSecondFactor({ strategy: "email_code", code })
            : await signIn.attemptFirstFactor({ strategy: "email_code", code });
        if (result.status === "complete") {
          await setSignInActive({ session: result.createdSessionId });
          router.push(destination);
          return;
        }
        setErrorMessage(`Could not complete sign in (${result.status}).`);
      } catch (err) {
        setErrorMessage(describeError(err));
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!signUp || !setSignUpActive) return;

    try {
      const result = await signUp.attemptEmailAddressVerification({ code });

      if (result.status === "complete") {
        await setSignUpActive({ session: result.createdSessionId });
        // Records *when* the user agreed and to which policy revision — the
        // sign-up form's checkbox is `required`, so reaching this point
        // already implies assent; this just makes it durable server-side.
        // Best-effort: a failure here must never block the user from
        // finishing sign-up, since the account already exists.
        try {
          await apiClient.post("/users/me/consent");
        } catch {
          // Non-fatal — consent can be recorded on a later authenticated request.
        }
        router.push(destination);
        return;
      }

      setErrorMessage(`Could not complete sign up (${result.status}).`);
    } catch (err) {
      setErrorMessage(describeError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleVerificationCancel = () => {
    setVerificationFlow("sign-up");
    setVerification(null);
    setErrorMessage(null);
    setInfoMessage(null);
  };

  const handleModeSwitch = (next: AuthMode) => {
    setMode(next);
    setVerificationFlow("sign-up");
    setVerification(null);
    setErrorMessage(null);
    setInfoMessage(null);
  };

  // Keep the form hidden until we know for sure this visitor is signed out —
  // avoids a flash of the sign-in form for someone who's about to be redirected.
  if (!authLoaded || isSignedIn) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <SignInPage
      mode={mode}
      onModeSwitch={handleModeSwitch}
      heroImageSrc={HERO_IMAGE}
      onPasswordSubmit={handlePasswordSubmit}
      onMagicLink={() => {}}
      onGoogleSignIn={handleGoogleSignIn}
      onLinkedInSignIn={handleLinkedInSignIn}
      onGithubSignIn={handleGithubSignIn}
      onResetPassword={() => {}}
      verification={verification}
      onVerificationSubmit={handleVerificationSubmit}
      onVerificationCancel={handleVerificationCancel}
      errorMessage={errorMessage}
      infoMessage={infoMessage}
      loading={loading || !clerkReady}
    />
  );
}
