import type { NextConfig } from "next";

const backendOrigin = (
  process.env.DJANGO_API_ORIGIN || "http://127.0.0.1:8000"
).replace(/\/$/, "");
const nextConfig: NextConfig = {
  experimental: { cpus: 2 },
  poweredByHeader: false,
  // Preserve Django's terminal API slashes so session/CSRF POSTs never redirect.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backendOrigin}/api/:path*/` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};
export default nextConfig;
