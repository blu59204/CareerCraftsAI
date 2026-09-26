"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

const STORAGE_KEY = "cc-cookie-notice-ack";

/**
 * Today the only cookies this app sets are strictly-necessary session
 * cookies (Clerk auth) — no analytics or advertising cookies exist yet
 * (see /privacy). Strictly-necessary cookies don't legally require opt-in
 * consent under GDPR/ePrivacy, so this is a one-time acknowledgement
 * banner, not a consent gate — dismissing it doesn't change what's set.
 * If a tracking/analytics cookie is ever added, this needs to become a
 * real accept/reject choice with a way to opt out.
 */
export function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setVisible(true);
    } catch {
      // Private browsing / blocked storage — fail open (don't show a banner
      // that can never be dismissed).
    }
  }, []);

  const dismiss = () => {
    setVisible(false);
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // Nothing to persist; it'll just show again next visit.
    }
  };

  if (!visible) return null;

  return (
    <div
      role="region"
      aria-label="Cookie notice"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-border bg-card/95 px-4 py-4 backdrop-blur-xl sm:px-6"
    >
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-3 sm:flex-row sm:justify-between">
        <p className="text-sm text-muted-foreground">
          We use only the cookies required to keep you signed in — no advertising or tracking cookies.
          See our{" "}
          <Link href="/cookies" className="text-primary hover:underline">
            Cookie Policy
          </Link>{" "}
          for details.
        </p>
        <LiquidGlassButton tone="primary" size="sm" onClick={dismiss} className="shrink-0">
          Got it
        </LiquidGlassButton>
      </div>
    </div>
  );
}
