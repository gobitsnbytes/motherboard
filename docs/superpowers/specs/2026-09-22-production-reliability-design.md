# Production reliability patch design

## Goal

Remove the observed intermittent "backend offline" failures without replacing the current VPS architecture. Ship the work as small atomic commits that can be reviewed and rolled back independently.

## Scope

### 1. Non-blocking API startup

The FastAPI lifespan must establish only resources required to accept requests. Slow external initialization will run after the server starts, with bounded timeouts and logged failure states. Liveness must not depend on Discord, Redis, email, or other remote services.

### 2. Bounded health reporting

`/health` remains a cheap process liveness check. `/health/ready` checks required dependencies. `/api/health/status` returns partial component results under a fixed overall deadline; a slow Discord or database detail query must not stall the entire response. Component failures are represented as degraded status instead of being swallowed.

### 3. Safe onboarding reads

Onboarding synchronization must not serialize expired SQLAlchemy entities after a commit. The route will refresh or reload its response data after mutation, and regression coverage will reproduce the PostgreSQL-style post-commit expiration failure.

### 4. Truthful frontend proxy errors

The Next.js API proxy will use a bounded request timeout. Timeout, upstream connection failure, and upstream HTTP errors will remain distinguishable. Dashboard status copy will reserve "offline" for connection failure and use "slow" or "degraded" for timeouts and unhealthy components.

### 5. Verified replacement deployment

Deployment will start a replacement API instance on a temporary local port, verify liveness and readiness, switch Nginx to it, reload Nginx, and then retire the old instance. Any failure before or after the switch restores the previous upstream and leaves the old process serving traffic. Database migrations remain a pre-switch operation and must be backward compatible with the running release.

### 6. Diagnostics and tests

Add regression tests for startup behavior, health deadlines and partial results, onboarding post-commit serialization, proxy timeout mapping, and deployment rollback logic where practical. API middleware will log route, status, duration, and a request identifier for server errors without logging credentials or request bodies.

### 7. Certificate renewal repair

Inspect the broken `mail.gobitsnbytes.org` renewal entry against the active certificate lineage. Repair only missing or stale file references, run `certbot renew --dry-run`, and preserve the current certificate until validation passes.

### 8. Calendar maintenance response

Since no service listens on port 3100, Nginx will stop proxying `cal.gobitsnbytes.org` to a dead upstream. It will return a deliberate `503 Service Unavailable` maintenance response with `Retry-After`, avoiding noisy connection failures and misleading generic gateway errors.

## Patch sequence

1. FastAPI startup and health behavior.
2. Onboarding transaction regression.
3. Frontend proxy and status semantics.
4. Request-level error logging.
5. Replacement-process deployment and rollback.
6. Certbot and calendar production configuration.
7. Final regression suite, review, production verification, and memory update.

Each patch must pass its focused tests before the next begins. The final push occurs only after the full backend and relevant frontend checks pass.

## Safety and rollback

No production database data is rewritten. Existing service configuration is backed up before edits. Nginx configuration is tested before reload. Certificate changes require a successful dry run. The deployment switch retains the previous API process and upstream configuration until the replacement passes both health checks.

## Success criteria

- API liveness responds during external dependency delays.
- Detailed health returns within its deadline with component-level states.
- Onboarding case listing cannot fail from post-commit expiration.
- The UI distinguishes timeout, degradation, authentication failure, and connection failure.
- Deploying a healthy release causes no observable API outage; a failed replacement keeps the old release live.
- Certbot dry-run succeeds.
- Calendar returns a controlled maintenance response rather than a gateway error.
