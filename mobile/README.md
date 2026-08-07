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

1. `EXPO_PUBLIC_API_URL` — env var at start time (or `mobile/.env`)
2. `expo.extra.apiBaseUrl` in `app.json`
3. `http://localhost:8000` (fallback)

A phone running Expo Go **cannot reach `localhost`** — on the phone, localhost
*is* the phone. Copy `.env.example` to `.env` and set your machine's LAN
address:

```bash
cp .env.example .env       # then edit EXPO_PUBLIC_API_URL
npx expo start -c
```

`EXPO_PUBLIC_*` values are inlined at bundle time, so **`-c` (clear cache) is
required** after changing them — otherwise the old value keeps running and the
change looks like it did nothing.

(Same idea as the web app's `VITE_API_URL`.)

### When the phone says "Can't reach Kolabo"

Three things have to be true, and they fail in this order of likelihood.

**1. The API must accept non-local callers.** `uvicorn app.main:app --reload`
— the command in `backend/README.md` — binds `127.0.0.1`, reachable from the
dev machine and nowhere else. For device testing run:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Docker already binds `0.0.0.0`, so `docker compose up` needs nothing.

**2. The phone must have a route to the machine.** Both on the same Wi-Fi —
not one on mobile data, and not a "guest" network, which isolates clients from
each other by design. On Windows the network profile must be **Private**; the
firewall drops inbound connections on Public profiles whatever the rules say.
To open the port, in an elevated shell:

```powershell
netsh advfirewall firewall add rule name="Kolabo API 8000" dir=in action=allow protocol=TCP localport=8000
```

**3. The app must be pointed at that address**, per the section above.

**Isolate it in ten seconds:** open `http://<machine-ip>:8000/health` in the
*phone's* browser. If that loads, the network is fine and the problem is the
env var (step 3). If it does not, it is step 1 or 2, and no app change will
help.

No route at all — locked-down office Wi-Fi, phone on mobile data? Run
`ngrok http 8000` and set `EXPO_PUBLIC_API_URL` to the ngrok URL, with
`npx expo start --tunnel` for Metro itself. That works from anywhere.

**Not CORS.** CORS is a browser rule and a native app is not a browser. A
request that fails on the phone but works in the web app is an address or
firewall problem every time.

### Do not keep this repo inside OneDrive / iCloud / Dropbox

A synced folder and `node_modules` are a bad pair, and Metro is where it shows
up. The usual symptom is a red screen quoting a 500 from the dev server:

```
Metro has encountered an error: Cannot read properties of undefined
(reading 'transformFile') ... node_modules\metro\src\Bundler.js
```

Nothing is wrong with the code. Sync clients virtualise files ("Files
On-Demand"), so Metro opens a placeholder instead of the real module, or hits
a file locked mid-upload — and a dependency graph built from that is
incoherent. Hundreds of thousands of small files also make sync itself
miserable.

The durable fix is to keep the working copy on a local path, `C:\dev\kolabo`
or similar. Cloud-syncing a git repository buys nothing that the remote does
not already do, and costs this.

To recover an installation that has already been corrupted this way:

```powershell
# stop Metro first
Remove-Item -Recurse -Force node_modules
npm install
npx expo install --fix   # realign package versions with the SDK
npx expo start -c
```

If the repo must stay in OneDrive, right-click the folder → **Always keep on
this device**, and pause syncing while working. That reduces the failure rate;
it does not remove it.

## What's here

The whole marketplace loop, both sides of it.

- `src/lib/` — `api.ts` (fetch client + `ApiError`, mirrors the web contract),
  `auth.tsx` (token/role in the device keystore via `expo-secure-store`),
  `errorMessages.ts` (ported EN/FR refusal catalog + `errorText`), `config.ts`,
  plus the shapes and rules ported from web: `campaignTypes`, `contractTypes`,
  `orders` (the 48 h clock), `lifecycle` (the derived "completed" rule),
  `notifications`, `imagePicker`, `platforms`, `countries`, `dates`.
- `src/i18n.ts`, `src/strings.ts`, `src/lib/notificationBodies.ts` — bilingual
  copy; `fr: typeof en` makes EN/FR key parity a compile error to break.
- `src/navigation/` — a signed-out stack (Login, Register, Verify OTP, Forgot
  password) and a signed-in stack. Which one renders is a function of auth
  state, so login/logout swap the whole tree.
- `src/screens/` — **creator**: profile (avatar, portfolio, socials, packages),
  open board with filters, invitations and negotiation, contracts,
  deliverables, disputes, earnings. **Brand**: business profile, discover
  creators, storefront + direct order, campaign create/edit/publish, proposal
  threads, spend. **Both**: notifications.
- `src/components/ui.tsx` — shared, themed primitives (Screen, Card, Field,
  buttons, banners, choice groups).

Still web-only: messaging, admin, and the cart (multi-creator checkout).

## Checks

```bash
npm run typecheck   # tsc --noEmit
```

CI runs the same typecheck on every PR (the `mobile` job). On-device behaviour
is verified manually in Expo Go — there is no simulator in CI.
