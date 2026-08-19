import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16 blocks cross-origin requests to dev resources (/_next/*) by
  // default. It treats "localhost" as canonical, so hitting the dev server by
  // IP -- 127.0.0.1, or the LAN address from a phone on the same wifi -- gets
  // 403s on every chunk and a failed HMR socket. The page loads but React
  // never hydrates, which looks like a broken app rather than a config block.
  //
  // The LAN entries matter for testing the Android app against `pnpm dev`.
  // Dev-only; production builds ignore this.
  allowedDevOrigins: [
    "127.0.0.1",
    "localhost",
    "192.168.0.0/16",
    "10.0.0.0/8",
    "172.16.0.0/12",
  ],
};

export default nextConfig;
