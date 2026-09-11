"use client";

/**
 * Backend auth-token bridge.
 *
 * Historically this read the Supabase access token; the app now authenticates
 * with Clerk, so this returns the Clerk **session token** (RS256 JWT whose
 * `sub` is the Clerk user id). The exported name and signature are unchanged so
 * every caller (`lib/api.ts`, `lib/sse.ts`) keeps working untouched.
 *
 * This is a plain async function rather than a hook, so it cannot use
 * `useAuth()`. It reads the Clerk singleton that `<ClerkProvider>` installs on
 * `window`, which is the supported way to reach a session outside React.
 */

type ClerkSessionLike = {
  getToken: (options?: { template?: string }) => Promise<string | null>;
};

type ClerkGlobal = {
  loaded?: boolean;
  session?: ClerkSessionLike | null;
};

const CLERK_READY_TIMEOUT_MS = 5_000;
const CLERK_POLL_INTERVAL_MS = 50;

function readClerk(): ClerkGlobal | null {
  if (typeof window === "undefined") return null;
  return (window as unknown as { Clerk?: ClerkGlobal }).Clerk ?? null;
}

/**
 * clerk-js is injected asynchronously, so a call made during the first paint
 * can land before `window.Clerk` exists. Poll briefly instead of returning a
 * spurious `null` that would send an unauthenticated request.
 */
async function waitForClerk(): Promise<ClerkGlobal | null> {
  const deadline = Date.now() + CLERK_READY_TIMEOUT_MS;

  while (Date.now() < deadline) {
    const clerk = readClerk();
    if (clerk?.loaded) return clerk;
    await new Promise((resolve) => setTimeout(resolve, CLERK_POLL_INTERVAL_MS));
  }

  return readClerk();
}

/**
 * Returns the current Clerk session JWT for `Authorization: Bearer` headers,
 * or null when there is no active session.
 */
export async function getSupabaseAuthToken(): Promise<string | null> {
  try {
    const clerk = await waitForClerk();
    const session = clerk?.session;
    if (!session) return null;
    return await session.getToken();
  } catch {
    return null;
  }
}
