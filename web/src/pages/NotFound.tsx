import { useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";

/* The catch-all. Until this existed an unmatched URL matched no route and
   rendered NOTHING: no header, no footer, an empty div, which reads as a
   broken site rather than as a wrong address.

   IT IS A SOFT 404 AND THAT IS A DECISION, not an oversight. nginx answers
   every unmatched path with index.html and HTTP 200 (web/nginx.conf), and it
   cannot do better without knowing which client routes are real, which would
   mean a second copy of App.tsx's route table living in a file no test covers
   and CI never builds. The cheap-looking alternative is worse rather than
   better: try_files with =404 plus error_page 404 /index.html answers 404 for
   EVERY client route, because none of them are files on disk, and that
   includes /legal/privacy and /legal/terms, which exist precisely so that
   crawlers and app-store reviewers can read them.

   So the status stays 200 and the meta tag below is what keeps a 200 out of a
   search index. */
export default function NotFound() {
  const { t } = useTranslation();

  /* The first place this app touches the document head. Added on mount and
     removed on unmount rather than written into index.html, because
     index.html is shared by every route and all the others are real pages. */
  useEffect(() => {
    const tag = document.createElement("meta");
    tag.name = "robots";
    tag.content = "noindex";
    document.head.appendChild(tag);
    return () => {
      document.head.removeChild(tag);
    };
  }, []);

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 640 }}>
        <h1>{t("notFound.title")}</h1>
        <p className="muted">{t("notFound.body")}</p>
        <div style={{ display: "flex", gap: 12, marginTop: 20, flexWrap: "wrap" }}>
          <Link className="btn btn-primary" to="/">{t("notFound.home")}</Link>
          <Link className="btn btn-ghost" to="/discover">{t("notFound.discover")}</Link>
          <Link className="btn btn-ghost" to="/legal/privacy">{t("notFound.privacy")}</Link>
        </div>
      </div>
    </Layout>
  );
}
