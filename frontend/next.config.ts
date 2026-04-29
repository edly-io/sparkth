import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = isDev
  ? {
      trailingSlash: true,
      async rewrites() {
        return [
          { source: "/api/:path*", destination: "http://localhost:7727/api/:path*" },
          { source: "/ai/:path*", destination: "http://localhost:7727/ai/:path*" },
        ];
      },
    }
  : {
      output: "export",
      trailingSlash: true,
    };

export default nextConfig;
