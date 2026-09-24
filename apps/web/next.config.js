const { withSentryConfig } = require("@sentry/nextjs/config");
const { version } = require("./package.json");

// One release for browser, Node.js, and Edge bundles and for the uploaded
// source maps: bnb-web@<version>+<sha12> when the build knows its commit.
const commitSha = process.env.VERCEL_GIT_COMMIT_SHA || process.env.GITHUB_SHA || process.env.GIT_SHA || "";
const sentryRelease =
  process.env.SENTRY_RELEASE || `bnb-web@${version}${commitSha ? `+${commitSha.slice(0, 12)}` : ""}`;
const sentryEnvironment =
  process.env.SENTRY_ENVIRONMENT ||
  process.env.VERCEL_ENV ||
  (process.env.NODE_ENV === "production" ? "production" : "development");
const sentryAuthToken = process.env.SENTRY_AUTH_TOKEN;

/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@bnb/ui"],
  env: {
    NEXT_PUBLIC_SENTRY_RELEASE: sentryRelease,
    NEXT_PUBLIC_SENTRY_ENVIRONMENT: sentryEnvironment,
  },
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
  org: process.env.SENTRY_ORG || "gobitsnbytes-foundation",
  project: process.env.SENTRY_PROJECT || "motherboard-frontend",
  authToken: sentryAuthToken,
  release: { name: sentryRelease, create: Boolean(sentryAuthToken) },
  // Upload (then delete) source maps only when the private build token exists.
  sourcemaps: { disable: !sentryAuthToken, deleteSourcemapsAfterUpload: true },
  widenClientFileUpload: true,
  telemetry: false,
  silent: !process.env.CI,
});
