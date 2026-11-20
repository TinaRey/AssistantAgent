import type { NextConfig } from "next";

// The browser only talks to Next.js (same origin); /api/* is proxied to FastAPI.
// This keeps the session cookie httpOnly and avoids CORS entirely.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};
export default nextConfig;
