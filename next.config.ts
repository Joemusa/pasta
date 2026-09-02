import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  agentRules: false,
  async redirects() {
    return [
      { source: "/intelligence", destination: "/", permanent: false },
      { source: "/competitors", destination: "/", permanent: false },
      { source: "/retailers", destination: "/", permanent: false },
      { source: "/macro", destination: "/", permanent: false },
      { source: "/opportunities", destination: "/", permanent: false },
      { source: "/internal", destination: "/", permanent: false },
      { source: "/ask", destination: "/", permanent: false },
      { source: "/brief", destination: "/", permanent: false },
    ];
  },
};

export default nextConfig;
