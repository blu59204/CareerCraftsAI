import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  if (typeof window === "undefined") {
    throw new Error(
      "createClient() called server-side — use createServerClient() from @/lib/supabase/server instead"
    );
  }
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
