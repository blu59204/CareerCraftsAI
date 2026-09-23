/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  compress: true,
  poweredByHeader: false,
  reactStrictMode: true,
  turbopack: {
    root: __dirname,
  },

  // Optimize images
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 60 * 60 * 24 * 30, // 30 days
    remotePatterns: [
      {
        protocol: "https",
        hostname: "i.ytimg.com",
      },
    ],
  },

  // Proxy /api/v1/* → backend. Browser only ever talks to localhost:3000,
  // so the frontend bundle never needs to know the backend's docker DNS
  // name (which the host browser can't resolve).
  //
  // In docker (frontend container), BACKEND_URL=http://backend:8000
  // is set by docker-compose and rewrites go through the docker network.
  //
  // In local dev (`npm run dev` on the host), set BACKEND_URL=http://localhost:8000
  // in frontend/.env.local so the rewrite points at the host-local uvicorn.
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://backend:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },

  // Cache public assets. Next.js manages /_next/static cache headers itself,
  // which keeps dev chunks from being pinned across Fast Refresh rebuilds.
  async headers() {
    return [
      {
        source: "/:all*(svg|jpg|png|webp|avif|woff2)",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
