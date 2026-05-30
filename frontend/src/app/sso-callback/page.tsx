"use client";

import { useClerk, useSignIn, useSignUp } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

function CallbackLoading({ error }: { error?: string }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 text-center">
      <div className="space-y-3">
        <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="text-sm font-medium text-foreground">
          {error ? "Authentication failed" : "Completing sign in..."}
        </p>
        {error && <p className="max-w-md text-xs text-muted-foreground">{error}</p>}
        <div id="clerk-captcha" />
      </div>
    </main>
  );
}

export default function SSOCallbackPage() {
  const clerk = useClerk();
  const { signIn } = useSignIn();
  const { signUp } = useSignUp();
  const router = useRouter();
  const hasRun = useRef(false);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    async function finish() {
      if (!clerk.loaded || !signIn || !signUp || hasRun.current) return;
      hasRun.current = true;

      const goHome = async ({ decorateUrl }: { decorateUrl: (url: string) => string }) => {
        const url = decorateUrl("/dashboard");
        if (url.startsWith("http")) window.location.href = url;
        else router.replace(url);
      };

      if (signIn.status === "complete") {
        const { error: finalizeError } = await signIn.finalize({ navigate: goHome });
        if (finalizeError) throw finalizeError;
        return;
      }

      if (signUp.status === "complete") {
        const { error: finalizeError } = await signUp.finalize({ navigate: goHome });
        if (finalizeError) throw finalizeError;
        return;
      }

      if (signIn.isTransferable) {
        const { error: transferError } = await signUp.create({ transfer: true });
        if (transferError) throw transferError;
        if ((signUp.status as string) === "complete") {
          const { error: finalizeError } = await signUp.finalize({ navigate: goHome });
          if (finalizeError) throw finalizeError;
          return;
        }
      }

      if (signUp.isTransferable) {
        const { error: transferError } = await signIn.create({ transfer: true });
        if (transferError) throw transferError;
        if ((signIn.status as string) === "complete") {
          const { error: finalizeError } = await signIn.finalize({ navigate: goHome });
          if (finalizeError) throw finalizeError;
          return;
        }
      }

      if (signIn.existingSession || signUp.existingSession) {
        const sessionId = signIn.existingSession?.sessionId || signUp.existingSession?.sessionId;
        if (sessionId) {
          await clerk.setActive({ session: sessionId, navigate: goHome });
          return;
        }
      }

      router.replace(
        `/login?error=${encodeURIComponent(
          `OAuth needs another step. Signin: ${signIn.status}; signup: ${signUp.status}`,
        )}`,
      );
    }

    finish().catch((err) => {
      setError(err instanceof Error ? err.message : "OAuth callback failed");
    });
  }, [clerk, router, signIn, signUp]);

  return <CallbackLoading error={error} />;
}
