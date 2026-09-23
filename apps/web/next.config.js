/** @type {import('next').NextConfig} */
const { withSentryConfig } = require("@sentry/nextjs/config");

const nextConfig = {
  transpilePackages: ["@bnb/ui"],
  eslint: {
    ignoreDuringBuilds: true,
  },
  async rewrites() {
    return {
      fallback: [
        {
          source: "/api/:path*",
          destination: `${process.env.API_URL || "http://api:8000"}/api/:path*`,
        },
      ],
    };
  },
};

module.exports = withSentryConfig(nextConfig, {
  org: "gobitsnbytes-foundation",
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  silent: !process.env.CI,
});
