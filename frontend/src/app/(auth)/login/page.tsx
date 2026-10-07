"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
// `@clerk/nextjs/legacy` exposes the classic custom-flow hooks
// ({ isLoaded, signIn, setActive }). Nothing here renders Clerk UI.
import { useSignIn, useSignUp } from "@clerk/nextjs/legacy";
import { useAuth, useSession } from "@clerk/nextjs";
import type { OAuthStrategy } from "@clerk/nextjs/types";
import {
  SignInPage,
  type AuthMode,
  type AuthPasswordSubmitData,
  type AuthResetPasswordData,
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

// Set when the member ticks Terms on the sign-up form and then picks
// Google/LinkedIn/GitHub, so the account can be finished on return without a
// second consent page. Only that affirmative click writes it.
const OAUTH_TERMS_KEY = "careercraft:oauth_terms_accepted_at";
const OAUTH_TERMS_TTL_MS = 30 * 60 * 1000;

function takeOAuthTermsAccepted(): boolean {
  try {
    const at = Number(sessionStorage.getItem(OAUTH_TERMS_KEY));
    sessionStorage.removeItem(OAUTH_TERMS_KEY);
    return at > 0 && Date.now() - at < OAUTH_TERMS_TTL_MS;
  } catch {
    return false;
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
  const { session } = useSession();
  const { isLoaded: signInLoaded, signIn, setActive: setSignInActive } = useSignIn();
  const { isLoaded: signUpLoaded, signUp, setActive: setSignUpActive } = useSignUp();

  const [mode, setMode] = useState<AuthMode>("sign-in");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [verification, setVerification] = useState<AuthVerificationState | null>(null);
  // Which flow the code field is completing — a new account, or a sign-in whose
  // only enabled first factor is an emailed code.
  const [verificationFlow, setVerificationFlow] = useState<"sign-up" | "sign-in" | "sign-in-second" | "reset">("sign-up");
  const resetPasswordRef = useRef("");
  const [secondStrategy, setSecondStrategy] = useState<"totp" | "backup_code" | "phone_code" | "email_code">("totp");
  const [secondChoices, setSecondChoices] = useState<Array<{ strategy: "totp" | "backup_code" | "phone_code" | "email_code"; phoneNumberId?: string }>>([]);
  async function prepareSecond(strategy: typeof secondStrategy, email: string, phoneNumberId?: string) {
    if (!signIn) return;
    if (strategy === "phone_code" && phoneNumberId) await signIn.prepareSecondFactor({ strategy, phoneNumberId });
    else if (strategy === "email_code") await signIn.prepareSecondFactor({ strategy });
    setSecondStrategy(strategy);
    setVerificationFlow("sign-in-second");
    setVerification({ email, title: "Confirm it's you", description: strategy === "totp" ? "Enter a code from your authenticator app." : strategy === "backup_code" ? "Enter one of your saved backup codes." : strategy === "phone_code" ? "Enter the code sent to your phone." : "Enter the code sent to your email." });
  }
  async function beginSecond(email: string) {
    if (!signIn) return;
    const choices = (signIn.supportedSecondFactors ?? []).filter((factor) => ["totp", "backup_code", "phone_code", "email_code"].includes(factor.strategy)) as typeof secondChoices;
    setSecondChoices(choices);
    const first = choices.find((factor) => factor.strategy === "totp") ?? choices[0];
    if (!first) throw new Error("No supported verification method is available. Contact support.");
    await prepareSecond(first.strategy, email, first.phoneNumberId);
  }
  const handleResetPassword = async ({ email, password }: AuthResetPasswordData) => {
    if (!signIn) return;
    setLoading(true); setErrorMessage(null);
    try {
      await signIn.create({ strategy: "reset_password_email_code", identifier: email });
      resetPasswordRef.current = password;
      setVerificationFlow("reset");
      setVerification({ email, description: `Enter the password reset code sent to ${email}.` });
    } catch (err) { setErrorMessage(describeError(err)); }
    finally { setLoading(false); }
  };
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
  //
  // A session can also exist but be merely "pending" (Clerk session tasks,
  // e.g. instance-required MFA enrollment) — isSignedIn is false in that
  // state, so without this check the user fell through to the sign-in form,
  // where every signIn/signUp call fails with "You're already signed in"
  // and they're stuck. Route pending sessions to /session-task instead.
  useEffect(() => {
    if (!authLoaded) return;
    if (session?.currentTask) {
      router.replace("/session-task");
      return;
    }
    if (isSignedIn) {
      router.replace(destination);
    }
  }, [authLoaded, isSignedIn, session, destination, router]);

  // OAuth "account transfer": /sso-callback sends a brand-new Google/GitHub/
  // LinkedIn identity (no matching CareerCraft account) here via
  // continueSignUpUrl. Clerk marks the in-progress signIn's first factor
  // verification "transferable" but does NOT itself create the account —
  // the app has to notice that status and call signUp.create({ transfer:
  // true }) to actually finish it. Without this, a first-time OAuth sign-in
  // just lands back on an empty password form with no account ever created,
  // which looked like the whole login flow silently failing.
  //
  // That transfer also needs Clerk's Legal Consent field, which OAuth has no
  // way to collect mid-redirect — and on a later visit (transfer already
  // consumed) `firstFactorVerification` is no longer "transferable" at all,
  // leaving the sign-up stuck at status "missing_requirements" needing
  // `legal_accepted` with nothing to retry it. Neither case may be completed
  // on the user's behalf: this effect only *detects* the condition and shows
  // an explicit consent screen (oauthConsentPending below); legalAccepted is
  // sent only from handleOAuthConsentConfirm, after the user checks the box.
  const transferDetectedRef = useRef(false);
  const oauthTransferableRef = useRef(false);
  const [oauthConsentPending, setOauthConsentPending] = useState(false);
  const [oauthConsentChecked, setOauthConsentChecked] = useState(false);

  async function completeOAuthSignUp(): Promise<boolean> {
    if (!signUp || !setSignUpActive) return false;
    setLoading(true);
    setErrorMessage(null);
    try {
      const result = oauthTransferableRef.current
        ? await signUp.create({ transfer: true, legalAccepted: true })
        : await signUp.update({ legalAccepted: true });
      if (result.status === "complete") {
        await setSignUpActive({ session: result.createdSessionId });
        try {
          await apiClient.post("/users/me/consent");
        } catch {
          // Non-fatal — consent can be recorded on a later authenticated request.
        }
        router.push(destination);
        return true;
      }
      setErrorMessage(`Could not finish creating your account (${result.status}).`);
    } catch (err) {
      setErrorMessage(describeError(err));
    } finally {
      setLoading(false);
    }
    return false;
  }

  useEffect(() => {
    if (mode !== "sign-up") return;
    if (!signInLoaded || !signUpLoaded || !signIn || !signUp) return;
    if (transferDetectedRef.current) return;

    const isTransferable = signIn.firstFactorVerification?.status === "transferable";
    const needsLegalConsent =
      signUp.status === "missing_requirements" &&
      (signUp.missingFields ?? []).includes("legal_accepted");
    if (!isTransferable && !needsLegalConsent) return;

    transferDetectedRef.current = true;
    oauthTransferableRef.current = isTransferable;
    if (takeOAuthTermsAccepted()) {
      // They ticked Terms on the sign-up form before choosing the provider.
      // If that fails, the consent screen offers a retry.
      void completeOAuthSignUp().then((done) => {
        if (!done) setOauthConsentPending(true);
      });
    } else {
      // Started from the sign-in form (no checkbox there): ask once.
      setOauthConsentPending(true);
    }
    // Runs once (transferDetectedRef); completeOAuthSignUp reads the same Clerk objects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, signInLoaded, signUpLoaded, signIn, signUp]);

  const handleOAuthConsentConfirm = async () => {
    if (!oauthConsentChecked) return;
    await completeOAuthSignUp();
  };

  const clerkReady = signInLoaded && signUpLoaded && !!signIn && !!signUp;

  const startOAuth = async (strategy: OAuthStrategy) => {
    if (!signIn) return;
    setLoading(true);
    setErrorMessage(null);

    if (mode === "sign-up") {
      // The form only lets this run once Terms is ticked (see SignInPage).
      try {
        sessionStorage.setItem(OAUTH_TERMS_KEY, String(Date.now()));
      } catch {
        // Without storage the return trip falls back to the consent screen.
      }
    }
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
    agreedToPolicies,
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
            await beginSecond(email);
            return;
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
        // The required Terms checkbox: stored on the Clerk user (legalAcceptedAt),
        // so consent is never asked a second time after sign-up.
        legalAccepted: agreedToPolicies === true,
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
    if (verificationFlow === "reset") {
      try {
        if (!signIn || !setSignInActive) return;
        const result = await signIn.attemptFirstFactor({ strategy: "reset_password_email_code", code, password: resetPasswordRef.current });
        resetPasswordRef.current = "";
        if (result.status === "complete") {
          await setSignInActive({ session: result.createdSessionId });
          router.push(destination);
        } else if (result.status === "needs_second_factor") await beginSecond(verification?.email ?? "");
        else setErrorMessage(`Could not reset password (${result.status}).`);
      } catch (err) { setErrorMessage(describeError(err)); }
      finally { setLoading(false); }
      return;
    }
    if (verificationFlow === "sign-in" || verificationFlow === "sign-in-second") {
      if (!signIn || !setSignInActive) return;
      try {
        // email_code serves as the first factor when password is disabled, and
        // as the second factor when Clerk wants ownership confirmed after a
        // correct password. Same code field, different Clerk call.
        const result =
          verificationFlow === "sign-in-second"
            ? await signIn.attemptSecondFactor({ strategy: secondStrategy, code })
            : await signIn.attemptFirstFactor({ strategy: "email_code", code });
        if (result.status === "complete") {
          await setSignInActive({ session: result.createdSessionId });
          router.push(destination);
          return;
        }
        if (result.status === "needs_second_factor") { await beginSecond(verification?.email ?? ""); return; }
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
    resetPasswordRef.current = "";
    setVerificationFlow("sign-up");
    setVerification(null);
    setErrorMessage(null);
    setInfoMessage(null);
  };

  const handleModeSwitch = (next: AuthMode) => {
    setMode(next);
    resetPasswordRef.current = "";
    setVerificationFlow("sign-up");
    setVerification(null);
    setErrorMessage(null);
    setInfoMessage(null);
  };

  // Keep the form hidden until we know for sure this visitor is signed out —
  // avoids a flash of the sign-in form for someone who's about to be redirected.
  if (!authLoaded || isSignedIn || session?.currentTask) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  // A brand-new OAuth identity has no equivalent of the password flow's
  // required Terms/Privacy checkbox, so collect the same affirmative consent
  // here before the account is ever created — legalAccepted is only sent
  // from handleOAuthConsentConfirm, never automatically.
  if (oauthConsentPending) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="w-full max-w-sm space-y-6 text-center">
          <h1 className="text-2xl font-semibold text-foreground">One more step</h1>
          <p className="text-sm text-muted-foreground">
            Review and accept our policies to finish creating your account.
          </p>
          {errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}
          <label className="flex items-start justify-center gap-3 text-left text-sm text-foreground/90">
            <input
              id="oauthAgreedToPolicies"
              type="checkbox"
              checked={oauthConsentChecked}
              onChange={(event) => setOauthConsentChecked(event.target.checked)}
              className="custom-checkbox mt-0.5 shrink-0"
            />
            <span>
              I agree to the{" "}
              <a
                href="/terms"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Terms of Service
              </a>{" "}
              and{" "}
              <a
                href="/privacy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Privacy Policy
              </a>
              .
            </span>
          </label>
          <button
            type="button"
            onClick={handleOAuthConsentConfirm}
            disabled={!oauthConsentChecked || loading}
            className="w-full rounded-2xl bg-primary py-4 font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-60"
          >
            {loading ? "Please wait…" : "Accept & continue"}
          </button>
        </div>
      </main>
    );
  }

  return (
    <SignInPage
      mode={mode}
      onModeSwitch={handleModeSwitch}
      heroImageSrc={HERO_IMAGE}
      onPasswordSubmit={handlePasswordSubmit}
      onMagicLink={async (email) => {
        if (!signIn) return;
        setLoading(true); setErrorMessage(null);
        try {
          const result = await signIn.create({ identifier: email });
          const factor = result.supportedFirstFactors?.find((f) => f.strategy === "email_code");
          if (!factor) throw new Error("Email code sign-in is unavailable. Use your password or a social provider.");
          await signIn.prepareFirstFactor({ strategy: "email_code", emailAddressId: (factor as { emailAddressId: string }).emailAddressId });
          setVerificationFlow("sign-in"); setVerification({ email });
        } catch (err) { setErrorMessage(describeError(err)); }
        finally { setLoading(false); }
      }}
      onGoogleSignIn={handleGoogleSignIn}
      onLinkedInSignIn={handleLinkedInSignIn}
      onGithubSignIn={handleGithubSignIn}
      onResetPassword={handleResetPassword}
      verification={verification}
      verificationAlternatives={verificationFlow === "sign-in-second" ? secondChoices.map((factor) => ({ label: factor.strategy === "totp" ? "Authenticator app" : factor.strategy === "backup_code" ? "Backup code" : factor.strategy === "phone_code" ? "Text message" : "Email code", onClick: async () => { setLoading(true); setErrorMessage(null); try { await prepareSecond(factor.strategy, verification?.email ?? "", factor.phoneNumberId); } catch (err) { setErrorMessage(describeError(err)); } finally { setLoading(false); } } })) : []}
      onVerificationSubmit={handleVerificationSubmit}
      onVerificationCancel={handleVerificationCancel}
      errorMessage={errorMessage}
      infoMessage={infoMessage}
      loading={loading || !clerkReady}
    />
  );
}
