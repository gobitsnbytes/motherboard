import * as Sentry from "@sentry/nextjs";

import { sharedSentryOptions } from "./sentry.shared";

Sentry.init({
  ...sharedSentryOptions,
  // The web DSN is public and inlined at build time. SENTRY_DSN is left to the
  // API, which shares the root .env with this app under Docker Compose.
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
});
