/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  compress: true,
  poweredByHeader: false,
  reactStrictMode: true,

  // Optimize images
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 60 * 60 * 24 * 30, // 30 days
  },

  // Reduce bundle size
  modularizeImports: {
    "lucide-react": {
      transform: "lucide-react/dist/esm/icons/{{kebabCase member}}",
    },
  },

  // Headers for caching static assets
  async headers() {
    return [
      {
        source: "/:all*(svg|jpg|png|webp|avif|woff2)",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
      {
        source: "/_next/static/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
    ];
  },

  experimental: {
    optimizePackageImports: ["lucide-react", "motion", "@radix-ui/react-dialog"],
  },
};

module.exports = nextConfig;
