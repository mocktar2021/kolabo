# Kolabo mobile

React Native app via Expo — single codebase for iOS + Android (Part 17 decision).

## Run it

```bash
npm install
npx expo start
```

Then open it in **Expo Go** on a phone (scan the QR), or press `a` / `i` for an
Android / iOS simulator.

### Pointing at the backend

The app reads the API base URL, in priority order, from:

1. `EXPO_PUBLIC_API_URL` — env var at start time
2. `expo.extra.apiBaseUrl` in `app.json`
3. `http://localhost:8000` (fallback)

A phone running Expo Go **cannot reach `localhost`** — that's the phone itself.
Point it at your machine's LAN address (or a tunnel) instead:

```bash
EXPO_PUBLIC_API_URL=http://192.168.1.20:8000 npx expo start
```

(Same idea as the web app's `VITE_API_URL`.)

## What's here

The **auth vertical** and its foundation:

- `src/lib/` — `api.ts` (fetch client + `ApiError`, mirrors the web contract),
  `auth.tsx` (token/role in the device keystore via `expo-secure-store`),
  `errorMessages.ts` (ported EN/FR refusal catalog + `errorText`), `config.ts`,
  `countries.ts`.
- `src/i18n.ts`, `src/strings.ts`, `src/theme.ts` — bilingual copy, device
  language detection, and the brand tokens from the web theme.
- `src/navigation/` — a signed-out stack (Login, Register, Verify OTP, Forgot
  password) and a signed-in stack (Dashboard placeholder). Which one renders is
  a function of auth state, so login/logout swap the whole tree.
- `src/components/ui.tsx` — shared, themed primitives (Screen, Card, Field,
  buttons, banners, choice group).

Creator screens (profile, briefs, contracts, deliverables, earnings) are the
next slice.

## Checks

```bash
npm run typecheck   # tsc --noEmit
```

CI runs the same typecheck on every PR (the `mobile` job). On-device behaviour
is verified manually in Expo Go — there is no simulator in CI.

<!-- Auth vertical: Register → OTP → Login → shell, plus password reset. -->
