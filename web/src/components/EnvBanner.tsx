import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { IS_PRODUCTION } from "../lib/env";

/* Loud on purpose. This is the one element on the page whose job is to be
   noticed before anything else is read, so it does not borrow a theme colour:
   nothing else in the app is this colour, which is what makes "am I on the
   dev box" answerable from a screenshot. */
const BAR: React.CSSProperties = {
  background: "#8a2b06",
  color: "#ffffff",
  textAlign: "center",
  padding: "7px 16px",
  fontSize: 13,
  fontWeight: 600,
  lineHeight: 1.4
};

/* Rendered by Layout, above the header, so it is the first thing on every
   page. Layout is the right home rather than main.tsx because all 30 pages
   import it individually (this app has no layout route), and main.tsx sits
   outside the router.

   THE CONSEQUENCE IS WORTH KNOWING: a future page that does not render Layout
   would silently lose the banner. */
export function EnvBanner() {
  const { t } = useTranslation();

  /* The crawler half, and the two measures do different jobs rather than one
     being a spare for the other. robots.txt, written per environment in
     web/Dockerfile, asks a crawler not to fetch the pages at all. This asks
     whatever did fetch one not to index it, which still matters because a URL
     somebody links to from outside can be indexed without ever being crawled.

     The hook runs unconditionally and decides inside, because a hook behind an
     early return is a hook that changes between renders. */
  useEffect(() => {
    if (IS_PRODUCTION) return;
    const tag = document.createElement("meta");
    tag.name = "robots";
    tag.content = "noindex";
    document.head.appendChild(tag);
    return () => {
      document.head.removeChild(tag);
    };
  }, []);

  if (IS_PRODUCTION) return null;
  return <div style={BAR}>{t("env.banner")}</div>;
}
