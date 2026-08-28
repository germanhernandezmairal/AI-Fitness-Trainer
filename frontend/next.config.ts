import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Hide the on-screen dev indicator so local screenshots/recordings for the
  // memoria and the README stay clean.
  devIndicators: false,
};

export default nextConfig;
