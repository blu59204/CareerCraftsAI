import type { MetadataRoute } from "next";

const SITE_URL = "https://careercraftsai.me";

// Everything under /(app) requires sign-in — an anonymous crawler gets
// redirected to /login anyway, so there's no content to index and no
// crawl budget worth spending here.
const AUTHENTICATED_PATHS = [
  "/dashboard",
  "/jobs",
  "/resume",
  "/agents",
  "/linkedin",
  "/leads",
  "/settings",
  "/company",
  "/email",
  "/interview",
  "/interview-prep",
  "/cover-letter",
  "/onboarding",
  "/applications",
  "/salary",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [...AUTHENTICATED_PATHS, "/sso-callback"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
