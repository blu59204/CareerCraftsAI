"use client";

import { useEffect } from "react";
import { apiClient } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type ProviderSession = {
  provider_token?: string | null;
  provider_refresh_token?: string | null;
  expires_at?: number | null;
  expires_in?: number | null;
};

export function GoogleOAuthSync() {
  useEffect(() => {
    let cancelled = false;

    async function syncGoogleTokens() {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const providerSession = session as (typeof session & ProviderSession) | null;
      const accessToken = providerSession?.provider_token;
      if (!accessToken || cancelled) return;

      const syncKey = `google-oauth-synced:${accessToken.slice(0, 18)}`;
      if (sessionStorage.getItem(syncKey)) return;

      await apiClient.post("/users/me/google-oauth", {
        access_token: accessToken,
        refresh_token: providerSession.provider_refresh_token ?? undefined,
        expires_at: providerSession.expires_at ?? undefined,
        expires_in: providerSession.expires_in ?? 3600,
      });
      sessionStorage.setItem(syncKey, "1");
    }

    syncGoogleTokens().catch(() => {
      // User can reconnect from Settings if provider token was not returned.
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}
