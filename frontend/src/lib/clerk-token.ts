"use client";

type ClerkTokenProvider = () => Promise<string | null>;

let tokenProvider: ClerkTokenProvider | null = null;

export function setClerkTokenProvider(provider: ClerkTokenProvider | null) {
  tokenProvider = provider;
}

export async function getClerkAuthToken() {
  if (!tokenProvider) return null;
  return tokenProvider();
}
