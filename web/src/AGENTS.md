# AGENTS.md — `web/src` (React frontend)

Vite + React + TypeScript frontend implementing the tri-shell UI: lists sidebar · center focus tabs · Copilot right rail.

## Layout & boundaries

- Top-level `*.tsx` — feature components (Chat, Market, Risk, News, Focus, Portfolio, Watchlist, Settings).
- `app/` — app shell, three-column layout, error boundary. `ui/` — shared reusable components. `hooks/` — React hooks (bootstrap, chat, data fetch, layout).
- `api.ts` / `apiSse.ts` — REST client and SSE streaming. Streaming state is immutable (`StreamState`) and rendered incrementally by `StreamFeed`.
- `settings/` + `settingsStore.ts` — persisted user settings (localStorage) with migration/validation.
- `locales/` + `i18n.tsx` — i18n. `styles/` + `index.css` — CSS-variable theming.
- `__tests__/` — Vitest + React Testing Library unit tests.

## Commands (run from `web/`)

```bash
npm run dev      # :5174
npm run build    # tsc && vite build — type errors block the build
npm run test     # vitest run
npm run lint     # eslint src/
```

## Risk routing

- `build` runs `tsc`, so type errors fail the build — keep types green, not just runtime behavior.
- `api.ts` and the app shell are the highest-churn files; add focused vitest tests instead of relying on build alone.
- Use the CSS-variable theme tokens rather than hardcoded colors.
- SSE state must stay immutable; don't mutate `StreamState` in place.
