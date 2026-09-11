"use client";

/**
 * Connects a Google account to the signed-in Clerk user so the Email agent can
 * use Gmail/Drive on their behalf.
 *
 * Clerk models this as an "external account" on the existing user. The Google
 * OAuth access/refresh tokens are held by Clerk and are read server-side by the
 * backend via Clerk's Backend API — they are never exposed to the browser.
 */

export const GMAIL_SCOPES = [
  "https://www.googleapis.com/auth/gmail.send",
  "https://www.googleapis.com/auth/gmail.readonly",
  // drive.file = least-privilege write: app can only see/manage files it creates.
  "https://www.googleapis.com/auth/drive.file",
];

type ExternalAccountResource = {
  verification?: { externalVerificationRedirectURL?: URL | string | null } | null;
};

type ClerkUserLike = {
  createExternalAccount: (params: {
    strategy: "oauth_google";
    redirectUrl?: string;
    additionalScopes?: string[];
  }) => Promise<ExternalAccountResource>;
};

type ClerkGlobal = { user?: ClerkUserLike | null };

export interface ConnectResult {
  error: { message: string } | null;
}

export async function connectGoogleForGmail(nextPath: string): Promise<ConnectResult> {
  if (typeof window === "undefined") {
    return { error: { message: "Google can only be connected from the browser." } };
  }

  const user = (window as unknown as { Clerk?: ClerkGlobal }).Clerk?.user;
  if (!user) {
    return { error: { message: "You must be signed in to connect Google." } };
  }

  try {
    const externalAccount = await user.createExternalAccount({
      strategy: "oauth_google",
      redirectUrl: `${window.location.origin}${nextPath}`,
      additionalScopes: GMAIL_SCOPES,
    });

    const redirectUrl = externalAccount.verification?.externalVerificationRedirectURL;
    if (!redirectUrl) {
      return { error: { message: "Google did not return an authorization URL." } };
    }

    window.location.href = redirectUrl.toString();
    return { error: null };
  } catch (err) {
    const clerkErrors = (err as { errors?: { longMessage?: string; message?: string }[] })?.errors;
    const first = clerkErrors?.[0];
    return {
      error: {
        message:
          first?.longMessage ||
          first?.message ||
          (err instanceof Error ? err.message : "Could not start Google connection."),
      },
    };
  }
}
