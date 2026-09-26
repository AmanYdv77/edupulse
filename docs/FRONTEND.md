# EduPulse Frontend Architecture & Developer Guide

The EduPulse web frontend is a high-performance, strictly-typed Single Page Application (SPA) built with **React 18**, **TypeScript (Strict Mode)**, **Vite**, and pure **CSS Design Tokens**.

It is served directly by Django at `/app/` under a strict Content-Security-Policy (CSP) with zero third-party external dependencies or CDN asset requests.

---

## 1. Architectural Principles

1. **Contract-Driven Typing:**
   - All API request and response types are generated automatically from the backend OpenAPI 3.0 specification (`docs/openapi.yaml`) using `openapi-typescript`.
   - Frontend and backend contracts cannot drift; schema changes immediately trigger TypeScript compile-time errors.
2. **Same-Origin Session Cookie Authentication:**
   - Uses same-origin Django session cookies (`sessionid`) and in-memory CSRF tokens (`X-CSRFToken`).
   - Zero tokens or credentials are stored in `localStorage` or `sessionStorage`.
3. **Capability-Based UI Shell:**
   - On session load, `GET /api/v1/me/` returns the authenticated user's role, academic scope label, and explicit list of granted UI capabilities (`view_own_results`, `log_habits`, `view_analytics`, `view_at_risk_roster`, `enter_internal_marks`, `manage_model_registry`).
   - The UI navigation dynamically filters navigation links and guards routes according to active capabilities.
4. **Accessible Design System & Zero Third-Party Requests:**
   - Pure CSS design tokens defined in `src/styles/tokens.css` with dark surface palettes.
   - Text contrast strictly complies with WCAG AA standards ($\ge 4.5:1$ contrast ratio).
   - Uses system font stacks (no runtime Google Fonts CDN network calls).
   - High-visibility focus rings (`:focus-visible`) and `prefers-reduced-motion` media queries.

---

## 2. Directory Structure

```text
frontend/
├── index.html              # SPA HTML entry point
├── package.json            # Pinned dependencies and build scripts
├── vite.config.ts          # Vite build config & dev proxy (/api -> 127.0.0.1:8000)
├── tsconfig.json           # Strict TypeScript configuration
├── vitest.config.ts        # Vitest test runner configuration
└── src/
    ├── api/
    │   ├── schema.d.ts     # Auto-generated OpenAPI TypeScript definitions
    │   └── client.ts       # Typed openapi-fetch client with CSRF interceptor
    ├── context/
    │   └── AuthContext.tsx # User session, capabilities, and login/logout state
    ├── components/
    │   ├── Layout/         # AppLayout, responsive sidebar, scope banner
    │   ├── RouteGuard.tsx  # Capability and authentication route guard
    │   └── ui/             # Reusable design system components
    │       ├── Button.tsx
    │       ├── Card.tsx
    │       ├── StatCard.tsx
    │       ├── DataTable.tsx
    │       ├── Badge.tsx
    │       ├── EmptyState.tsx
    │       ├── ErrorState.tsx
    │       ├── Skeleton.tsx
    │       └── ModelLabel.tsx
    ├── pages/              # Role-specific screens and fallback views
    │   ├── LoginPage.tsx
    │   ├── DashboardPage.tsx
    │   ├── UnauthorizedPage.tsx (403)
    │   └── NotFoundPage.tsx (404)
    ├── styles/
    │   ├── tokens.css      # Core design tokens and color variables
    │   └── base.css        # CSS reset, typography, and focus ring utilities
    ├── App.tsx             # Root router with capability-guarded routes
    └── main.tsx            # React DOM mounting entry point
```

---

## 3. Developer Commands

All commands should be executed from within the `frontend/` directory:

| Command | Purpose |
| :--- | :--- |
| `npm run dev` | Starts Vite local development server on `http://localhost:3000` (proxies `/api` to Django on `8000`). |
| `npm run build` | Runs TypeScript checks and builds the production bundle into `frontend/dist/`. |
| `npm run typecheck` | Runs `tsc --noEmit` to verify type safety across all files. |
| `npm run lint` | Runs ESLint on TypeScript and React code. |
| `npm test` | Runs the unit test suite using Vitest and React Testing Library. |
| `npm run gen:api` | Regenerates `src/api/schema.d.ts` from `../docs/openapi.yaml`. |

---

## 4. Production Serving & Content-Security-Policy

When deployed or running through Django:
1. `npm run build` outputs optimized production assets into `frontend/dist/`.
2. Django's `SPAIndexView` in `backend/apps/core/spa.py` serves `frontend/dist/index.html` at `/app/` and handles sub-route fallbacks (`/app/*`).
3. `SecurityHeadersMiddleware` automatically enforces the following security headers:
   - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none';`
   - `X-Content-Type-Options: nosniff`
   - `Referrer-Policy: same-origin`
