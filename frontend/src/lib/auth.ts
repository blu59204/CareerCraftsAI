import { auth as clerkAuth, currentUser as clerkCurrentUser } from "@clerk/nextjs/server";

export async function currentUser() {
  return clerkCurrentUser();
}

export async function auth() {
  const session = await clerkAuth();
  return {
    userId: session.userId,
    session: null,
    token: await session.getToken(),
  };
}
