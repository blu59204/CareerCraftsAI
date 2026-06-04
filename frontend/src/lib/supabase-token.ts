"use client";

import { createClient } from "@/lib/supabase";

/**
 * Returns the current Supabase access token (JWT) for Authorization headers,
 * or null when there is no active session. Reads the session directly from the
 * browser Supabase client so callers never depend on a registered provider.
 */
export async function getSupabaseAuthToken(): Promise<string | null> {
  try {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  } catch {
    return null;
  }
}
