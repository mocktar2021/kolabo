/* Loading Cloudflare's Turnstile widget, once, for whichever form asks first.

   THE SITE KEY IS IN THE SOURCE, and that is not an oversight. It is public
   by construction: it ships inside every page that renders the widget and
   Cloudflare's own documentation has you put it in the HTML. The secret key,
   which is the half that matters, lives in deploy/.env and is read only by
   the backend. web/Dockerfile makes exactly this argument about the Google
   client id a few lines down from where this one would have gone.

   NOT A BUILD ARG, unlike VITE_API_URL and VITE_GOOGLE_CLIENT_ID, and the
   reason is that those two differ per box while this one does not: the
   Turnstile site is configured with both hostnames, so production and the dev
   box hand back the same key. Threading a third ARG through web/Dockerfile,
   docker-compose.prod.yml and the preflight check to carry a constant would
   be three more places to get wrong for no value. If a second site ever
   exists, it becomes an ARG then.

   ONE SCRIPT TAG, ONE PROMISE. Two forms on one page, or a form that mounts
   twice, must not fetch api.js twice: the second load would re-register the
   global and orphan any widget the first had drawn. The promise is cached at
   module scope, so every caller after the first awaits the same load.

   EXPLICIT RENDER, not the data-attribute form. The widget has to be drawn
   into a div React owns, after React has put it on the page, which is what
   turnstile.render(element, ...) is for. The implicit form scans the document
   on load and would find nothing in a single page app. */

export const SITE_KEY = "0x4AAAAAAFjMpIIISaJ4TZem";

const SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

/* The part of Cloudflare's global this app uses. Hand written rather than
   pulled from a types package: three methods, and a dependency whose only
   job is to describe them is a dependency to keep current for nothing. */
export type TurnstileApi = {
  render: (
    element: HTMLElement,
    options: {
      sitekey: string;
      callback?: (token: string) => void;
      "error-callback"?: () => void;
      "expired-callback"?: () => void;
      theme?: "auto" | "light" | "dark";
      size?: "normal" | "flexible" | "compact";
    }
  ) => string;
  reset: (widgetId?: string) => void;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let loading: Promise<TurnstileApi | null> | null = null;

/* Resolves with the API, or with null if the script cannot be fetched.

   NULL RATHER THAN A REJECTION, because every caller's answer to a failure is
   the same and it is not "crash the signup form": render nothing, send no
   token, and let the server decide what an absent token means. A blocked
   script, an ad blocker, a captive portal or a country-level block of
   challenges.cloudflare.com must not be the reason somebody cannot create an
   account. */
export function loadTurnstile(): Promise<TurnstileApi | null> {
    if (window.turnstile) return Promise.resolve(window.turnstile);
    if (loading) return loading;

    loading = new Promise((resolve) => {
      const script = document.createElement("script");
      script.src = SCRIPT_URL;
      script.async = true;
      script.defer = true;
      script.onload = () => resolve(window.turnstile ?? null);
      script.onerror = () => resolve(null);
      document.head.appendChild(script);
    });
    return loading;
}
