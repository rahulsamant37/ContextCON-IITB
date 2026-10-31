import type { NextConfig } from "next";

const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

// Client-driven app (live progress stream, interactive tables): Cache Components / partial prefetching are intentionally off.
const nextConfig: NextConfig = {
  devIndicators: false,
  // The browser only ever talks to this origin; /api/* is proxied to the FastAPI server so the HttpOnly session cookie
  // is first-party for fetches, downloads and the EventSource progress stream.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
