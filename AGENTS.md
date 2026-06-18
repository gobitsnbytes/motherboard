# bnb-motherboard — Agent Build Instructions

> **Before starting any phase:** Run `bunx skills find <topic>` to locate relevant skill documentation for the task at hand (e.g. `bunx skills find drizzle orm`, `bunx skills find nextjs app router`, `bunx skills find discord oauth`). For Python/FastAPI backend tasks, verify with `bunx skills find fastapi` and `bunx skills find fastapi-patterns`. Use the outputs to guide implementation — do not guess at APIs.
>
> **Anti-hallucination rule:** After every 3–4 files created or every major subsystem completed, stop and search your context window (context 7 or equivalent) for the latest state of relevant interfaces, schemas, and type contracts before continuing. Write code against what actually exists in the codebase, not against memory.
>
> **Memory persistence rule:** Every agent invocation must document tasks completed, decisions made, codebase insights, and current progress in [MEMORY.md](file:///d:/motherboard/MEMORY.md). Update this file at the end of each session or major step so that future agents have a continuous record of the project's evolution.
>
> **AI Agent Skill-Specific Guidelines:**
> - **`brainstorming`**: MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements, and design before implementation.
> - **`prd`**: Generate high-quality Product Requirements Documents (PRDs) for software systems and AI-powered features. Includes executive summaries, user stories, technical specifications, and risk analysis.
> - **`ui-ux-pro-max`**: MUST use this before any UI/UX work (layouts, styling, animations, product types, guidelines).
> - **`impeccable`**: Use when the user wants to design, redesign, shape, critique, audit, polish, clarify, distill, harden, optimize, adapt, animate, colorize, extract, or otherwise improve a frontend interface (covers UX review, visual hierarchy, cognitive load, accessibility, micro-interactions, responsive behavior, theming, design systems/tokens, etc. Not for backend-only tasks).
> - **`neobrutalism`**: Use when designing or implementing user interfaces with the neobrutalist aesthetic, including bold borders, custom hard shadows, high-contrast layouts, and brandkit integrations.
> - **`code-reviewer`**: MUST use this skill towards the end of every task, and always before a push. Always perform atomic commits.
> - **`fastapi-patterns`**: FastAPI best practices covering project structure, Pydantic v2 schemas, dependency injection, async handlers, authentication, authorization, transactional service layers, and testing with httpx and pytest.
> - **`fastapi`**: FastAPI best practices and conventions. Use when working with FastAPI APIs and Pydantic models for them. Keeps FastAPI code clean and up to date with the latest features and patterns, updated with new versions. Write new code or refactor and update old code.
> - **`frontend-patterns`**: MUST use for all frontend/UI work.
> - **`database-migrations-sql-migrations`**: SQL database migrations with zero-downtime strategies for PostgreSQL, MySQL, and SQL Server. Focus on data integrity and rollback plans.
> - **`react-patterns` & `react-performance`**: MUST use when writing, reviewing, or refactoring React/Next.js components for styling, hooks discipline, server/client boundaries, and performance optimization.
> - **`nextjs-best-practices`**: Next.js App Router principles. Server Components, data fetching, routing patterns.
> - **`finance-billing-ops`**: Evidence-first revenue, pricing, refunds, team-billing, and billing-model truth workflow for ECC. Use when the user wants a sales snapshot, pricing comparison, duplicate-charge diagnosis, or code-backed billing reality instead of generic payments advice.
> - **`memory-md-management`**: Use when checking, auditing, updating, improving, or maintaining project memory files (such as `MEMORY.md`, `CLAUDE.md`, or creating one).
> - **`deployment-patterns` & `devops-rollout-plan`**: MUST use for all DevOps, Docker, CI/CD, rollout plans, and rollback/deployment strategy work.
> - **`security-review`**: MUST use when adding authentication, handling user input, working with secrets, creating API endpoints, or implementing sensitive features.
> - **`token-efficiency`**: Use to reduce token waste by 40-60% through anti-sycophancy rules, tool-call budgets, one-pass coding, task profiles, and read-before-write enforcement.
> - **`humaniser`**: Use while writing basically anything to remove signs of AI-generated writing and ensure natural phrasing.
> - **`ai-agent-development`**: Use for all AI agent work (CrewAI, LangGraph, custom agents).
> - **`vibe-code-cleanup` & `vibe-code-auditor`**: Use at all times for security and hardening once a task is done.
> - **`safety-guard`**: Use when working on production systems or running agents autonomously to prevent destructive operations.
> - **`plan-orchestrate`**: Use/suggest always for multi-step plan development.

***

## Repository Documentation Index

This index serves as the directory for all workspace-wide and subsystem-specific markdown documents. Refer to each document for its designated purpose:

* **[CLAUDE.md](file:///d:/motherboard/CLAUDE.md)**: Developer quick-start guide, setting up standard tools, workspace layouts, command conventions, and backend environments.
* **[MEMORY.md](file:///d:/motherboard/MEMORY.md)**: Dynamic agent state-tracker logging project phase status, completed tasks, and architectural decisions.
* **[README.md](file:///d:/motherboard/README.md)**: Main user-facing landing page and setup guide detailing project features, monorepo directory layout, and docker-compose requirements.
* **[apps/api/README.md](file:///d:/motherboard/apps/api/README.md)**: Subsystem-specific README for the FastAPI backend application.
* **[docs/design.md](file:///d:/motherboard/docs/design.md)**: Integrated brand specifications and design system tokens. Defines the community naming rules, brand logos, typography, HSL color palettes, Neo-Brutalist styling guidelines, and creative standards.
* **[docs/cors_security_guide.md](file:///d:/motherboard/docs/cors_security_guide.md)**: Reference guide outlining CORS vulnerabilities, safety protocols, and testing suites for whitelisted origin validation.
* **[docs/legal_governance_rules.md](file:///d:/motherboard/docs/legal_governance_rules.md)**: Reference guide consolidating corporate entity details, board structures, local fork onboarding checklists, financial UPI/cash routing restrictions, and webhook authorization secrets.
* **[docs/roadmap.md](file:///d:/motherboard/docs/roadmap.md)**: Five-stage project timeline mapping development goals from Stage 1 (Finance & Operations) to Stage 5 (T.B.D.).
* **[docs/techspec.md](file:///d:/motherboard/docs/techspec.md)**: Unified technical specification for the FastAPI/Next.js stack, mapping out DB tables, API router structures, async authorization middleware, event bus, and provisioning worker specs.

### Finance & Ledger Module (RazorpayX)

The **Ledger + Banking system** for GOBITSNBYTES FOUNDATION is powered by [RazorpayX](https://razorpay.com/x/) and its API.

* **Frontend:** `/finance` route in `apps/web` (currently shows "Coming Soon").
* **Backend:** `/api/finance/*` router in `apps/api` (health check and info endpoints live; full ledger integration planned).
* **Router file:** [apps/api/app/routers/finance.py](file:///d:/motherboard/apps/api/app/routers/finance.py)
* **Page file:** [apps/web/app/finance/page.tsx](file:///d:/motherboard/apps/web/app/finance/page.tsx)

### IAM Module (Identity & Access Management)

The IAM module evaluates user/group permissions using the async SQLAlchemy session engine. Completed in Phase 2.

* **Principal resolver** (`apps/api/app/iam/principal.py`) — resolves user + group memberships
* **Policy evaluator** (`apps/api/app/iam/policy.py`) — `can`, `require_permission`, `batch_can`
* **Audit writer** (`apps/api/app/iam/audit.py`) — non-committing audit log inserts
* **Constants** (`apps/api/app/iam/constants.py`) — `SYSTEM_GROUPS` + `CORE_PERMISSIONS`
* **API router** (`apps/api/app/routers/iam.py`) — CRUD for permissions, grants, groups, memberships, Discord role mappings
* **Tests** (`apps/api/tests/test_iam_policy.py`) — Super Admin, expiration, global/resource matching
* **Schemas** (`apps/api/app/schemas/iam.py`) — Pydantic v2 request/response validation
