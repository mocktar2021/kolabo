/* The Turnstile checkbox, on the three forms a stranger can submit.

   IT NEVER BLOCKS THE FORM, and that is the most important thing about it.
   The submit button is not gated on having a token, and nothing here refuses
   to render if Cloudflare is unreachable. A third party script must not be
   able to stop somebody creating an account on Kolabo, whether because an ad
   blocker ate it, a captive portal swallowed it, the network dropped, or the
   widget is simply still thinking. What happens on a missing token is a
   SERVER decision: app/core/turnstile.py verifies a token that arrives and,
   separately and only when told to, refuses a request without one. The client
   supplies what it can and says nothing about what that means.

   THAT IS ALSO WHAT MAKES LOCAL DEVELOPMENT WORK. A Turnstile site lists the
   hostnames it covers, and localhost is not one of ours, so the widget errors
   on a laptop. It reports no token, the form submits anyway, and the backend
   on that laptop has no secret key configured and asks for nothing.

   THE TOKEN IS SPENT ON USE. Cloudflare issues it once, it expires after five
   minutes, and a replay answers timeout-or-duplicate. So a form that submits,
   fails for some unrelated reason and is submitted again must draw a fresh
   one: that is what `resetSignal` is for. The parent increments it after each
   attempt, successful or not. A number rather than an imperative ref because
   the parent already re-renders on that attempt, and a prop is easier to see
   than a method call somebody has to remember to make. */
import { useEffect, useRef } from "react";
import { SITE_KEY, loadTurnstile } from "../lib/turnstile";

export function TurnstileWidget({
  onToken,
  resetSignal = 0
}: {
  onToken: (token: string | null) => void;
  resetSignal?: number;
}) {
  const holder = useRef<HTMLDivElement | null>(null);
  const widgetId = useRef<string | null>(null);
  /* Held in a ref so the mount effect can call the latest one without listing
     it as a dependency and re-drawing the widget on every parent render. */
  const report = useRef(onToken);
  report.current = onToken;

  useEffect(() => {
    let cancelled = false;
    let api: Awaited<ReturnType<typeof loadTurnstile>> = null;

    loadTurnstile().then((loaded) => {
      api = loaded;
      if (cancelled || !loaded || !holder.current) return;
      widgetId.current = loaded.render(holder.current, {
        sitekey: SITE_KEY,
        callback: (token) => report.current(token),
        /* Both failure paths report the same thing, because they mean the
           same thing to the form: there is no token to send. An expired one
           is not a failure the person caused and there is nothing for them to
           do about it. */
        "error-callback": () => report.current(null),
        "expired-callback": () => report.current(null),
        theme: "auto",
        /* Flexible rather than normal, because a fixed 300px widget overflows
           the auth card on a narrow phone, which is most of this audience. */
        size: "flexible"
      });
    });

    return () => {
      cancelled = true;
      if (api && widgetId.current) api.remove(widgetId.current);
      widgetId.current = null;
    };
  }, []);

  useEffect(() => {
    /* Nothing to reset on the first render, and resetting a widget that has
       not been drawn yet throws inside Cloudflare's code. */
    if (resetSignal === 0 || !widgetId.current || !window.turnstile) return;
    window.turnstile.reset(widgetId.current);
    report.current(null);
  }, [resetSignal]);

  return <div ref={holder} style={{ marginBottom: 14 }} />;
}
