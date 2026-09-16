import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ensureGoogleIdentity,
  googleConfigured,
  noteButtonClicked,
  registerCredentialHandler
} from "../lib/googleSignIn";

/* Google's own button, drawn by Google, or nothing at all.

   IT RENDERS NOTHING WHEN THE CLIENT ID IS UNSET, and that is the whole
   contract rather than a nicety. Without an id there is no audience Google
   could address a token to, so a button here would open a chooser and then
   fail on the server with auth_google_unavailable: a control that exists only
   to refuse. Same rule the rest of the platform applies to a provider nobody
   configured. See lib/googleSignIn.ts, and note that the id is baked into the
   bundle at BUILD time, so an unset one means the image was built without it.

   THE MARKUP IS GOOGLE'S, NOT OURS. renderButton writes into the div below,
   which is why there is no label, no icon and no .btn class here. Google's
   branding terms are about their button specifically, and a hand drawn
   lookalike is how an app ends up with a sign in control that is subtly wrong
   in four languages. The cost is that it does not inherit the app's type scale
   and cannot be styled, so it sits inside a wrapper that centres it.

   THE WIDTH IS MEASURED RATHER THAN GUESSED. The button takes a pixel width,
   not a percentage, so a fixed number is either narrower than the form on a
   laptop or wider than the screen on a phone. The wrapper's own width is
   measured once on mount and clamped to what Google accepts. It does not
   follow a later resize, which is Google's own guidance and is the same
   compromise every embedder makes. */

/* Google's stated bounds for the width option. 400 is their documented
   maximum; the floor is ours, because below about 200 the localised label is
   clipped rather than wrapped. */
const MIN_WIDTH = 200;
const MAX_WIDTH = 400;

type Props = {
  /* Handed the encoded ID token. Kept in a ref below so that a callback which
     closes over screen state (the role and the country on the register form,
     say) is never the stale one Google was initialised with. */
  onCredential: (credential: string) => void;
  /* Which of Google's four labels to ask for. The wording is theirs and is
     already translated by them, which is the main reason to let them draw it:
     "Se connecter avec Google" is not a string this repo has to own. */
  text?: "signin_with" | "signup_with" | "continue_with";
};

export function GoogleSignInButton({ onCredential, text = "signin_with" }: Props) {
  const { i18n, t } = useTranslation();
  /* Stable for the life of the component and unique on the page, which is
     exactly what the dispatcher in lib/googleSignIn.ts needs: it is what goes
     into the button's `state` and what comes back on the credential. */
  const buttonId = useId();
  const holder = useRef<HTMLDivElement | null>(null);
  const handler = useRef(onCredential);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    handler.current = onCredential;
  }, [onCredential]);

  useEffect(() => {
    if (!googleConfigured()) return;
    let live = true;
    const unregister = registerCredentialHandler(buttonId, (credential) => {
      handler.current(credential);
    });
    ensureGoogleIdentity()
      .then((google) => {
        if (!live || !holder.current) return;
        const measured = holder.current.clientWidth || MAX_WIDTH;
        google.renderButton(holder.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "rectangular",
          logo_alignment: "left",
          text,
          /* Google translates its own label from this. i18n.language is
             "fr" or "en" here, which is what the option takes. */
          locale: i18n.language,
          width: Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, measured)),
          state: buttonId,
          click_listener: () => noteButtonClicked(buttonId)
        });
      })
      .catch(() => {
        /* The id is configured and the script did not arrive: a blocked
           third party domain, or a connection that dropped. Said out loud
           rather than left as a gap where a button should be, because the
           person is looking for a control somebody told them is there. The
           email and password form underneath still works, which is what the
           sentence points at. */
        if (live) setFailed(true);
      });
    return () => {
      live = false;
      unregister();
    };
  }, [buttonId, i18n.language, text]);

  if (!googleConfigured()) return null;

  return (
    <div>
      <div ref={holder} style={{ display: "flex", justifyContent: "center", minHeight: 44 }} />
      {failed && <div className="hint">{t("auth.googleScriptFailed")}</div>}
    </div>
  );
}

/* The "or" between the Google button and the email form.

   A separate export because both auth screens draw it and neither should own
   it, and because it is the one piece of chrome around the button that IS
   ours. Hidden along with the button when the provider is unconfigured: a rule
   between one thing and nothing is a line across an empty card. */
export function GoogleDivider() {
  const { t } = useTranslation();
  if (!googleConfigured()) return null;
  return (
    <div
      aria-hidden="true"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        margin: "18px 0",
        color: "var(--muted)",
        fontSize: 12.5
      }}
    >
      <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
      {t("auth.googleOr")}
      <span style={{ flex: 1, height: 1, background: "var(--line)" }} />
    </div>
  );
}
