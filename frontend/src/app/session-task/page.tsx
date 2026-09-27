"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@clerk/nextjs";
import { TaskChooseOrganization, TaskResetPassword, TaskSetupMFA } from "@clerk/nextjs";

const DEFAULT_DESTINATION = "/dashboard";

/**
 * Resolves Clerk session tasks (https://clerk.com/docs/guides/configure/session-tasks) —
 * e.g. instance-required MFA enrollment — that leave a session "pending"
 * after sign-in/sign-up completes. /login only checks for a fully "active"
 * session, so without this route a pending session has nowhere to go: Clerk
 * rejects further signIn/signUp calls with "You're already signed in" while
 * the user is stuck looking at the login form. These task components are
 * Clerk's own prebuilt UI (QR codes, TOTP, backup codes) — not worth
 * hand-rolling for a single unavoidable step.
 */
export default function SessionTaskPage() {
  const { isLoaded, session } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (isLoaded && !session?.currentTask) {
      router.replace(DEFAULT_DESTINATION);
    }
  }, [isLoaded, session, router]);

  if (!isLoaded || !session?.currentTask) return null;

  switch (session.currentTask.key) {
    case "setup-mfa":
      return <TaskSetupMFA redirectUrlComplete={DEFAULT_DESTINATION} />;
    case "choose-organization":
      return <TaskChooseOrganization redirectUrlComplete={DEFAULT_DESTINATION} />;
    case "reset-password":
      return <TaskResetPassword redirectUrlComplete={DEFAULT_DESTINATION} />;
    default:
      return null;
  }
}
