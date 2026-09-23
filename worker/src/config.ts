export function resolveInternalSecret(
  env: Record<string, string | undefined> = process.env
): string {
  const secret = env.INTERNAL_SECRET ?? env.APP_SECRET_KEY;
  if (!secret?.trim()) {
    throw new Error("INTERNAL_SECRET/APP_SECRET_KEY not set — refusing to start");
  }
  return secret;
}

export const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ?? process.env.BACKEND_URL ?? "http://backend:8000";
export const INTERNAL_SECRET = resolveInternalSecret();
