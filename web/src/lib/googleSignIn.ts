/* Signing in with Google, on the web: the client id, the script, and the one
   callback Google will let us have.

   WHAT THIS IS NOT. It is not the subsystem behind lib/socialPlatforms.ts and
   backend/app/modules/profiles/oauth.py. That one asks a creator for
   permission over their own Facebook Page and stores a token belonging to
   THEM, against an account that is already signed in. This one answers a
   different question entirely: who is at the door. Nothing here is a
   credential of ours, there is no redirect uri, no callback route and no
   client secret, because there is no server side code exchange. Google hands
   the browser an ID token, this module hands it to POST /auth/google, and
   backend/app/modules/auth/google.py decides whether to believe it.

   THE CLIENT ID COMES FROM VITE_GOOGLE_CLIENT_ID AND UNSET MEANS ABSENT. With
   no id there is no audience Google could stamp into a token, so the button
   would render, open a chooser, and fail on the server with
   auth_google_unavailable. A provider nobody configured is ABSENT rather than
   half working: the same rule the backend states for GOOGLE_CLIENT_IDS, the
   YouTube key, the Meta credentials and the FedaPay keys. googleConfigured()
   is what every caller asks before drawing anything.

   IT IS BAKED IN AT BUILD TIME, NOT READ AT RUNTIME, exactly like
   VITE_API_URL. Vite substitutes import.meta.env.* into the bundle during
   `vite build`, so there is no process environment left to read when the
   browser runs it. Adding the variable to a running container's environment
   changes nothing at all: web/Dockerfile has to take it as a build ARG and
   deploy/docker-compose.prod.yml has to pass it there, and the image has to be
   REBUILT rather than restarted. Both of those were changed with this file;
   deploy/.env on the server is the third piece and has to be edited by hand.

   ONE initialize() FOR THE WHOLE PAGE, AND WHY THERE IS A REGISTRY BELOW.
   google.accounts.id.initialize is global and holds exactly one callback, so a
   second component calling it with its own callback silently steals the first
   one's. The account screen shows three proof controls at once (the email
   form, the phone form and the password form), which is precisely the shape
   that breaks: three buttons, one callback, and the wrong form receives the
   token. So initialize is called ONCE with a dispatcher, every button
   registers under an id, and renderButton carries that id in `state`, which
   Google returns on the credential. The click listener records the same id as
   a fallback for the case where `state` does not come back.

   Verified against Google's current documentation rather than from memory:
   the script is https://accounts.google.com/gsi/client, the button is drawn by
   google.accounts.id.renderButton(element, options), and the callback receives
   an object whose `credential` is the encoded JWT ID token. */
import { api, ApiError, type TokenResponse } from "./api";

/* What Google hands back when somebody finishes the chooser. `credential` is
   the ID token and is the only field this app reads a value out of; `state` is
   the button id we asked for, and is how the dispatcher knows which control
   was used. */
export type GoogleCredentialResponse = {
  credential?: string;
  select_by?: string;
  state?: string;
};

/* The four calls this app makes, and deliberately not a transcription of
   Google's whole surface. A hand written declaration rather than a types
   package: the package is one more dependency in a lockfile for four
   signatures, and a wrong hand written type fails the build here rather than
   somewhere subtle at runtime. */
type GoogleIdApi = {
  initialize(config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
  }): void;
  renderButton(
    parent: HTMLElement,
    options: {
      type?: "standard" | "icon";
      theme?: "outline" | "filled_blue" | "filled_black";
      size?: "large" | "medium" | "small";
      text?: "signin_with" | "signup_with" | "continue_with" | "signin";
      shape?: "rectangular" | "pill" | "circle" | "square";
      logo_alignment?: "left" | "center";
      width?: number;
      locale?: string;
      state?: string;
      click_listener?: () => void;
    }
  ): void;
  cancel(): void;
  disableAutoSelect(): void;
};

declare global {
  interface Window {
    google?: { accounts?: { id?: GoogleIdApi } };
  }
}

const SCRIPT_SRC = "https://accounts.google.com/gsi/client";

/* Trimmed, because an operator who leaves a stray space around the value in a
   .env file means the same thing as one who does not, and a client id with a
   space in it is one no token can ever be addressed to. Same treatment the
   backend gives the comma separated list it checks against. */
export const GOOGLE_CLIENT_ID = String(import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "").trim();

/* Asked before anything is drawn, everywhere. See the module note. */
export function googleConfigured(): boolean {
  return GOOGLE_CLIENT_ID !== "";
}

/* id -> what to do with a credential that arrives for it. */
const handlers = new Map<string, (credential: string) => void>();

/* The id of the button most recently clicked, used only when Google returns a
   credential with no `state` on it. One human can click one button at a time,
   so this is a safe tiebreak rather than a guess. */
let lastClicked: string | null = null;

export function registerCredentialHandler(
  id: string,
  handler: (credential: string) => void
): () => void {
  handlers.set(id, handler);
  return () => {
    handlers.delete(id);
    if (lastClicked === id) lastClicked = null;
  };
}

export function noteButtonClicked(id: string): void {
  lastClicked = id;
}

function dispatch(response: GoogleCredentialResponse): void {
  /* No credential means the person closed the chooser or Google refused to
     issue one. Nothing to do and nothing to say: they are looking at the
     button they just came from. */
  if (!response.credential) return;
  const id =
    typeof response.state === "string" && handlers.has(response.state)
      ? response.state
      : lastClicked;
  const handler = id ? handlers.get(id) : undefined;
  if (handler) handler(response.credential);
}

/* One in flight load for the whole page, and one initialize() behind it.
   Resolves with the API object so a caller can go straight to renderButton. */
let loading: Promise<GoogleIdApi> | null = null;

function injectScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      'script[data-kolabo-gsi="1"]'
    );
    if (existing) {
      /* Already on the page from an earlier mount. If it has finished, the
         API object is there and the caller's check below passes immediately;
         if it has not, these listeners join the same load. */
      if (window.google?.accounts?.id) {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("gsi script failed")));
      return;
    }
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.dataset.kolaboGsi = "1";
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => reject(new Error("gsi script failed")));
    document.head.appendChild(script);
  });
}

/* THE SCRIPT IS FETCHED ONLY WHEN A BUTTON IS ABOUT TO BE DRAWN, never at
   import time. Most sessions on this platform never see the login screen
   again after the first one, and these are metered connections: a third party
   script on every page load, for a button on two of them, is bandwidth spent
   on somebody else's behalf. */
export function ensureGoogleIdentity(): Promise<GoogleIdApi> {
  if (loading) return loading;
  loading = injectScript()
    .then(() => {
      const id = window.google?.accounts?.id;
      if (!id) throw new Error("gsi script loaded without accounts.id");
      /* ONE TAP IS NEVER PROMPTED. There is no prompt() call anywhere in this
         app, deliberately: a floating chooser that appears on its own over a
         page somebody is reading is an interruption, and on a narrow screen it
         covers the form it is offering to fill in. The button is the whole
         feature. */
      id.initialize({ client_id: GOOGLE_CLIENT_ID, callback: dispatch });
      return id;
    })
    .catch((err) => {
      /* Cleared so a later mount retries rather than inheriting a rejection
         from a moment when the network was down. */
      loading = null;
      throw err;
    });
  return loading;
}

/* What the two questions are worth once they have been asked. Both are
   optional on the request for the reason the backend schema gives: the call is
   made twice, and the second call carries the same token plus the answers. */
export type GoogleProfileAnswers = {
  role: string;
  country_code: string;
};

/* POST /auth/google, in one place so the two screens that call it cannot drift
   on the field names. The backend takes `id_token`, not `credential`, and the
   difference has no type checker behind it. */
export function signInWithGoogle(
  credential: string,
  answers?: GoogleProfileAnswers,
  referralCode?: string | null
): Promise<TokenResponse> {
  return api<TokenResponse>("/auth/google", {
    method: "POST",
    body: {
      id_token: credential,
      ...(answers ? { role: answers.role, country_code: answers.country_code } : {}),
      ...(referralCode ? { referral_code: referralCode } : {})
    }
  });
}

/* NOT AN ERROR, the first leg of a two step flow: a Google address with no
   Kolabo account behind it, and a server that cannot invent a country or a
   role. The caller asks both questions and calls again with the SAME token.
   Named here so no screen has to spell the code out and get it slightly
   wrong. */
export function needsProfileAnswers(err: unknown): boolean {
  return err instanceof ApiError && err.code === "auth_google_profile_required";
}

/* A password that did not work, which for a Google created account is what
   ALWAYS happens: its stored hash is of a secret nobody has ever seen, so
   login() refuses it exactly as it refuses a wrong one. The backend answers
   the same vague auth_bad_credentials either way on purpose, because a code
   that said "this address signs in with Google" would tell anyone holding a
   list of addresses which of them are registered here. The client cannot tell
   the two apart either, so it does not try: it points at the button, beside
   the field, and only after an attempt has failed. */
export function looksLikeWrongPassword(err: unknown): boolean {
  return err instanceof ApiError && err.code === "auth_bad_credentials";
}
