import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isProtectedRoute = createRouteMatcher([
  "/agents(.*)",
  "/company(.*)",
  "/dashboard(.*)",
  "/applications(.*)",
  "/email(.*)",
  "/interview(.*)",
  "/interview-prep(.*)",
  "/jobs(.*)",
  "/leads(.*)",
  "/linkedin(.*)",
  "/onboarding(.*)",
  "/resume(.*)",
  "/salary(.*)",
  "/settings(.*)",
]);

export default clerkMiddleware(async (auth, request) => {
  if (isProtectedRoute(request)) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set(
      "redirect_url",
      `${request.nextUrl.pathname}${request.nextUrl.search}`,
    );
    await auth.protect({ unauthenticatedUrl: loginUrl.toString() });
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest|mp4|webm)).*)",
    "/__clerk/(.*)",
  ],
};
