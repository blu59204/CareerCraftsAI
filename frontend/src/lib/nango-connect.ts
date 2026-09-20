"use client";

import { apiClient } from "@/lib/api";

export interface ConnectResult {
  error: { message: string } | null;
}

/** Start a short-lived Nango Connect session for Gmail. */
export async function connectGmail(returnPath: string): Promise<ConnectResult> {
  if (typeof window === "undefined") {
    return { error: { message: "Gmail can only be connected from a browser." } };
  }
  try {
    const { data } = await apiClient.post<{ connect_link?: string }>(
      "/integrations/connect-session",
      { provider: "gmail", return_path: returnPath },
    );
    if (!data.connect_link) {
      return { error: { message: "Could not start the secure Gmail connection." } };
    }
    window.location.assign(data.connect_link);
    return { error: null };
  } catch {
    return { error: { message: "Could not start the secure Gmail connection." } };
  }
}
