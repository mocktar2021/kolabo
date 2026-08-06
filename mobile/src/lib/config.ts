import Constants from "expo-constants";

/* Where the API lives.

   Resolved in priority order so the same build can point anywhere:
     1. EXPO_PUBLIC_API_URL — an env var read at bundle time (expo start /
        eas build), the usual way to switch environments.
     2. expo.extra.apiBaseUrl in app.json — a committed default per build
        profile.
     3. http://localhost:8000 — the docker-compose backend.

   NOTE FOR DEVICE TESTING: a phone running Expo Go cannot reach "localhost" —
   that resolves to the phone itself, not your laptop. Set EXPO_PUBLIC_API_URL
   to your machine's LAN address (e.g. http://192.168.1.20:8000) or a tunnel
   URL before `npx expo start`. The web app has the same rule via VITE_API_URL. */
const extra = (Constants.expoConfig?.extra ?? {}) as { apiBaseUrl?: string };

export const API_BASE: string =
  process.env.EXPO_PUBLIC_API_URL || extra.apiBaseUrl || "http://localhost:8000";
