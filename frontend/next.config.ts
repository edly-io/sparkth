import type { NextConfig } from "next";

const isProduction = process.env.NODE_ENV === "production";

// Production builds are static exports served by the FastAPI backend (same origin),
// so the frontend uses relative /api URLs. In development the dev server runs on
// :3000 and proxies those same relative URLs to the natively-running backend
// (default :7727, override with BACKEND_URL). Rewrites are unsupported with
// `output: "export"`, so they are only registered outside production.
const nextConfig: NextConfig = {
  output: isProduction ? "export" : undefined,
  trailingSlash: true,
  // Rewrites require the Next server and are unsupported under `output: "export"`,
  // so register the dev proxy only outside production.
  ...(isProduction
    ? {}
    : {
        // `trailingSlash: true` would otherwise force/normalize trailing slashes on
        // proxied /api calls, but the backend has mixed conventions (collection
        // routes need the trailing slash, e.g. /api/v1/user-plugins/, while
        // sub-resource routes must NOT have one). Skip the redirect in dev so the
        // rewrite forwards each /api path to the backend exactly as the client sent it.
        skipTrailingSlashRedirect: true,
        async rewrites() {
          const backend = process.env.BACKEND_URL ?? "http://localhost:7727";
          // Capture the remainder with a regex (.*) so the path — including any
          // trailing slash — is forwarded verbatim. A segment matcher (:path*)
          // drops the trailing slash, which breaks the backend's collection routes.
          return [
            { source: "/api/:path(.*)", destination: `${backend}/api/:path` },
            // Backend-served API docs (FastAPI). /docs and /redoc both fetch
            // /openapi.json, so it must be proxied too.
            { source: "/docs", destination: `${backend}/docs` },
            { source: "/redoc", destination: `${backend}/redoc` },
            { source: "/openapi.json", destination: `${backend}/openapi.json` },
          ];
        },
      }),
};

export default nextConfig;
