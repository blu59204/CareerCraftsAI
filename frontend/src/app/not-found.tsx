import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <div className="text-8xl font-bold text-primary/20">404</div>
      <h1 className="text-2xl font-medium">Page not found</h1>
      <p className="max-w-sm text-muted-foreground">
        This page doesn&apos;t exist. It may have moved or you followed a broken link.
      </p>
      <div className="flex gap-3">
        <Link
          href="/"
          className="rounded-full bg-primary px-5 py-2 text-sm font-medium text-primary-foreground"
        >
          Back to home
        </Link>
        <Link
          href="/dashboard"
          className="rounded-full border border-border bg-card px-5 py-2 text-sm font-medium text-foreground"
        >
          Dashboard
        </Link>
      </div>
    </div>
  );
}
