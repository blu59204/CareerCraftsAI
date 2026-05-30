import { createClient } from "@/lib/supabase/client";

export const GMAIL_SCOPES = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/gmail.send",
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/drive.readonly",
].join(" ");

export async function connectGoogleForGmail(nextPath: string) {
  const supabase = createClient();
  return supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}`,
      scopes: GMAIL_SCOPES,
      queryParams: { access_type: "offline", prompt: "consent" },
    },
  });
}
