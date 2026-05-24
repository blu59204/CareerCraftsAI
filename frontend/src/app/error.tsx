"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <div className="text-6xl">⚠</div>
      <h1 className="text-2xl font-medium">Something went wrong</h1>
      <p className="max-w-sm text-muted-foreground">
        An unexpected error occurred. Our team has been notified.
      </p>
      <div className="flex gap-3">
        <button
          onClick={reset}
          className="rounded-full bg-primary px-5 py-2 text-sm font-medium text-primary-foreground"
        >
          Try again
        </button>
        <a
          href="/"
          className="rounded-full border border-border bg-card px-5 py-2 text-sm font-medium text-foreground"
        >
          Go home
        </a>
      </div>
      {error.digest && (
        <p className="text-xs text-muted-foreground">Error ID: {error.digest}</p>
      )}
    </div>
  );
}
