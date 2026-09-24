FROM oven/bun:1.3.11-alpine AS base

WORKDIR /app

COPY package.json bun.lock turbo.json tsconfig.base.json tsconfig.json ./
COPY apps/web ./apps/web
COPY packages/ui ./packages/ui

RUN bun install --frozen-lockfile

FROM base AS builder

WORKDIR /app/apps/web

# Public Sentry values are inlined into the bundles at build time. The auth
# token arrives as a BuildKit secret so it never lands in an image layer:
#   docker build --secret id=sentry_auth_token,env=SENTRY_AUTH_TOKEN ...
ARG NEXT_PUBLIC_SENTRY_DSN=""
ARG NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE=""
ARG SENTRY_ENVIRONMENT=""
ARG SENTRY_RELEASE=""
ARG GIT_SHA=""

RUN --mount=type=secret,id=sentry_auth_token,required=false     SENTRY_AUTH_TOKEN="$(cat /run/secrets/sentry_auth_token 2>/dev/null || true)" bun run build

FROM oven/bun:1.3.11-alpine AS runner

ENV NODE_ENV=production

WORKDIR /app

COPY --from=base /app/node_modules ./node_modules
COPY --from=base /app/package.json ./package.json
COPY --from=base /app/bun.lock ./bun.lock
COPY --from=base /app/apps/web ./apps/web
COPY --from=base /app/packages/ui ./packages/ui
COPY --from=builder /app/apps/web/.next ./apps/web/.next

EXPOSE 3000

WORKDIR /app/apps/web

CMD ["bun", "run", "start"]
