import type { NextConfig } from "next";

// Client-driven app (live SSE, interactive tables): Cache Components / partial prefetching are intentionally off.
const nextConfig: NextConfig = {
  devIndicators: false,
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
