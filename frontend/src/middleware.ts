import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

/**
 * Public routes — anything NOT matched here requires a Clerk session.
 *
 * These regexes reproduce the previous `pathname.startsWith(prefix)` gate
 * one-for-one so the redirect behaviour is unchanged:
 *   - "/" and "/pricing" are exact-match public pages
 *   - everything else is a prefix match
 *
 * `/api/v1` is rewritten to the FastAPI backend by next.config.js, so the
 * browser hits this prefix directly. The middleware must not gate it — the
 * backend does its own auth from the `Authorization: Bearer <clerk jwt>` header.
 */
const isPublicRoute = createRouteMatcher([
  /^\/$/,
  /^\/pricing$/,
  /^\/login/,
  /^\/register/,
  // Clerk OAuth handshake lands here before a session exists.
  /^\/sso-callback/,
  /^\/api\/v1/,
  /^\/api\/webhooks/,
  /^\/about/,
  /^\/contact/,
  /^\/docs/,
  /^\/privacy/,
  /^\/terms/,
  /^\/status/,
  /^\/\.well-known/,
]);

/** Signed-in users are bounced off the auth entry pages. */
const isAuthEntryRoute = createRouteMatcher([/^\/login$/, /^\/register$/]);

export default clerkMiddleware(async (auth, request) => {
  const { userId } = await auth();

  if (!userId) {
    if (!isPublicRoute(request)) {
      const url = request.nextUrl.clone();
      url.pathname = "/login";
      url.searchParams.set("redirect_url", request.nextUrl.href);
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  if (isAuthEntryRoute(request)) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
