import type { NextConfig } from "next";

const apiProxy = process.env.API_PROXY_URL ?? "http://127.0.0.1:8000/api/v1";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{
      source: "/api/v1/:path*",
      destination: `${apiProxy}/:path*`,
    }];
  },
};
export default nextConfig;
