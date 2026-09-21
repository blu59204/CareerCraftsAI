"use client";

import { apiClient } from "@/lib/api";

export interface ConnectResult {
  error: { message: string } | null;
  popup?: Window;
}

export function openNangoConnectWindow(): Window | null {
  return window.open("", "nango-connect", "popup=yes,width=560,height=760");
}

/** Start a short-lived Nango Connect session for Gmail. */
export async function connectGmail(returnPath: string): Promise<ConnectResult> {
  if (typeof window === "undefined") {
    return { error: { message: "Gmail can only be connected from a browser." } };
  }
  const popup = openNangoConnectWindow();
  if (!popup) {
    return { error: { message: "Please allow popups to connect Gmail." } };
  }
  try {
    const { data } = await apiClient.post<{ connect_link?: string }>(
      "/integrations/connect-session",
      { provider: "gmail", return_path: returnPath },
    );
    if (!data.connect_link) {
      popup.close();
      return { error: { message: "Could not start the secure Gmail connection." } };
    }
    popup.location.href = data.connect_link;
    return { error: null, popup };
  } catch {
    popup.close();
    return { error: { message: "Could not start the secure Gmail connection." } };
  }
}
