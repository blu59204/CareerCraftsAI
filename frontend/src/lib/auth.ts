import { createClient } from "@/lib/supabase/server";

export async function currentUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user;
}

export async function auth() {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return {
    userId: session?.user.id ?? null,
    session,
  };
}
