/* The button that puts Kolabo on a home screen, bottom right, on every page.

   WHY A BUTTON AT ALL, when Chrome has its own install affordance: that
   affordance is an icon in the address bar on desktop and a line in an
   overflow menu on Android, and neither is somewhere a person looks. A brand
   or a creator who uses Kolabo weekly on a phone with patchy data is exactly
   who benefits from an icon on their home screen, and almost nobody finds the
   menu item. So the site asks, once, quietly, and takes no for an answer.

   THREE STATES, AND ONLY ONE OF THEM SHOWS ANYTHING.

   1. The browser fired beforeinstallprompt. Chrome, Edge and Samsung Internet
      do. The event is captured and its default suppressed, which is what stops
      Chrome's own mini-infobar and hands the timing to this component; the
      stored event is then fired on the tap. It can be used exactly once, so it
      is cleared afterwards whatever the person chose.

   2. Safari on iOS, which fires nothing and offers no API. The only route is
      Share then Add to Home Screen, by hand, so the button opens directions
      instead of pretending to install something. Detected by the absence of
      the event rather than by sniffing a version, with a user agent test for
      iOS itself because there is nothing else to test.

   3. Everywhere else, and after the app is installed: nothing renders.

   ALREADY INSTALLED IS CHECKED TWO WAYS because the platforms disagree.
   display-mode: standalone is the standard and is what Chrome answers to;
   navigator.standalone is Safari's own non-standard property and is the only
   signal on iOS. A person reading this inside the installed app must not be
   invited to install it again.

   DISMISSAL IS REMEMBERED PER BROWSER, in localStorage, wrapped in try/catch
   on both sides: private windows and blocked site data make these calls throw
   rather than fail quietly, and a storage failure must cost a hidden button at
   worst, never a blank page. appinstalled clears the flag's purpose entirely
   by unmounting the thing. */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

/* Not in lib.dom: beforeinstallprompt is a Chromium extension to the platform
   that no standard describes, so the shape it is used with is declared here
   rather than asserted as `any` at the call site. */
type InstallEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

const DISMISSED_KEY = "kolabo.install.dismissed";

function wasDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

function rememberDismissed() {
  try {
    localStorage.setItem(DISMISSED_KEY, "1");
  } catch {
    /* A browser that will not store this shows the button again next time,
       which is a smaller problem than a crash on a tap. */
  }
}

/* Running as an installed app rather than in a tab. Two checks because the
   two platforms answer in different places; see the note above. */
function isStandalone(): boolean {
  const iosStandalone = (window.navigator as Navigator & { standalone?: boolean }).standalone;
  return window.matchMedia("(display-mode: standalone)").matches || iosStandalone === true;
}

function isIos(): boolean {
  /* iPadOS reports itself as a Mac, so the touch point count is what tells an
     iPad from a laptop. Nothing else here is load bearing: the worst case of a
     wrong answer is a set of instructions shown to somebody who did not need
     them, behind a button they chose to tap. */
  const ua = window.navigator.userAgent;
  const iPadOs = /Macintosh/.test(ua) && window.navigator.maxTouchPoints > 1;
  return /iPhone|iPad|iPod/.test(ua) || iPadOs;
}

export function InstallPrompt() {
  const { t } = useTranslation();
  const [event, setEvent] = useState<InstallEvent | null>(null);
  const [hidden, setHidden] = useState(() => wasDismissed() || isStandalone());
  const [showIos, setShowIos] = useState(false);
  /* Settled after mount rather than during render: it reads the user agent,
     and keeping it out of the first render keeps this component honest about
     being a client-side thing. */
  const [ios, setIos] = useState(false);

  useEffect(() => {
    setIos(isIos());

    function onBeforeInstall(e: Event) {
      /* Suppress Chrome's own mini-infobar so the one invitation a person
         gets is this button and not two things asking at once. */
      e.preventDefault();
      setEvent(e as InstallEvent);
    }
    function onInstalled() {
      setEvent(null);
      setHidden(true);
    }

    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  /* Nothing to offer: either it is already installed, the person said no, or
     this is a browser that can neither prompt nor be told how. */
  if (hidden || (!event && !ios)) return null;

  async function install() {
    if (event) {
      await event.prompt();
      /* The outcome is deliberately not branched on. An accepted install
         fires appinstalled, which hides this; a declined one leaves the
         button where it was, because a person who closed the dialog by
         accident should be able to tap again. What cannot happen either way
         is reusing the event: it is spent. */
      await event.userChoice;
      setEvent(null);
      return;
    }
    setShowIos(true);
  }

  function dismiss() {
    rememberDismissed();
    setHidden(true);
  }

  return (
    <>
      <div style={{
        position: "fixed", right: 16, bottom: 16, zIndex: 40,
        display: "flex", alignItems: "center", gap: 6
      }}>
        {/* Smaller than a page button on purpose. This one floats over
            whatever somebody is reading, and on a narrow phone the French
            label is long enough that a full size pill would take most of the
            width and read as a bar rather than an offer. */}
        <button type="button" className="btn btn-primary" onClick={install}
          style={{ fontSize: 14, padding: "10px 16px", boxShadow: "0 6px 20px rgba(21,24,36,0.18)" }}>
          {t("install.button")}
        </button>
        {/* Outside the install button rather than inside it: nesting buttons
            is invalid HTML and breaks keyboard focus, the same reason the
            social tiles keep their remove control beside them. */}
        <button type="button" aria-label={t("install.dismiss")} title={t("install.dismiss")}
          onClick={dismiss}
          style={{
            width: 26, height: 26, borderRadius: 999, border: "1px solid var(--line)",
            background: "var(--surface)", color: "var(--muted)", cursor: "pointer",
            fontSize: 13, lineHeight: 1
          }}>
          x
        </button>
      </div>

      {showIos && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(21,24,36,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 20 }}
          onClick={() => setShowIos(false)}>
          <div className="card" style={{ maxWidth: 420, width: "100%" }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>{t("install.iosTitle")}</h3>
            <ol style={{ paddingLeft: 18, margin: "12px 0", lineHeight: 1.7, fontSize: 14 }}>
              <li>{t("install.iosStep1")}</li>
              <li>{t("install.iosStep2")}</li>
              <li>{t("install.iosStep3")}</li>
            </ol>
            <button type="button" className="btn btn-primary" onClick={() => setShowIos(false)}>
              {t("install.iosClose")}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
