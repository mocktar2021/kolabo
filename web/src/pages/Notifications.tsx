import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { getStoredRole, isBusinessLike, useAuth } from "../lib/auth";
import {
  PAGE_SIZE,
  relativeParts,
  routeForType,
  type AppNotification,
  type MarkAllRead
} from "../lib/notifications";

/* The whole history, for when the bell panel is not enough.

   WHY A PAGE AND NOT JUST THE PANEL. The panel holds a screenful, which is
   the right size for "what happened while I was away" and the wrong size for
   "when exactly did that contract get signed". The list endpoint is paged
   server-side (limit/offset, capped at 200) precisely so a client can walk
   back through it, and until this screen existed nothing did.

   NEITHER ROLE GUARD. Both sides of the market are notified about things —
   an invitation and a proposal are the same event read from two ends — so
   there is no role for this route to ask about.

   THE PAGING IS OFFSET PAGING AND IT IS SAFE, because the server sorts on
   created_at AND on id: two notifications raised in the same call (an escrow
   release tells both parties, a signature tells both) share a timestamp, and
   with one sort key a paged read could show a row twice and skip another. */
export default function NotificationsPage() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState<AppNotification[]>([]);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isBrand = isBusinessLike(getStoredRole());

  useEffect(() => {
    if (!token) return;
    let live = true;
    setLoading(true);
    // Trailing slash on purpose: the list route is @router.get("/") under the
    // /notifications prefix, so the path really is "/notifications/".
    api<AppNotification[]>(`/notifications/?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`, { token })
      .then((res) => { if (live) { setRows(res); setError(null); } })
      .catch(() => { if (live) setError(t("notif.loadFailed")); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [token, page, t]);

  function openRow(row: AppNotification) {
    if (!row.is_read) {
      setRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, is_read: true } : r)));
      api(`/notifications/${row.id}/read`, { method: "POST", token }).catch(() => undefined);
    }
    const to = routeForType(row.type, isBrand);
    if (to) navigate(to);
  }

  function markAll() {
    setRows((prev) => prev.map((r) => ({ ...r, is_read: true })));
    api<MarkAllRead>("/notifications/read-all", { method: "POST", token }).catch(() => undefined);
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  /* The API returns a page and no total, so "is there a next page" can only be
     answered by whether this one came back full. A short page is the last
     one; a page that is exactly full may or may not have anything after it,
     and offering the button costs one request to find out — which is cheaper
     than shipping a count nobody else needs on every read. */
  const hasMore = rows.length === PAGE_SIZE;
  const unreadOnPage = rows.some((r) => !r.is_read);

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 720 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h1 style={{ margin: 0 }}>{t("notif.title")}</h1>
          <button type="button" className="btn btn-ghost" disabled={!unreadOnPage} onClick={markAll}>
            {t("notif.markAll")}
          </button>
        </div>
        <p className="muted" style={{ marginTop: 6 }}>{t("notif.sub")}</p>
        {/* Said before the list rather than discovered by clicking: a
            notification has no id of the thing it is about, so a click opens
            the screen and not the row. A reader who expected the exact
            contract deserves to know why they got the list. */}
        <p className="muted" style={{ fontSize: 13.5 }}>{t("notif.routeNote")}</p>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {loading ? (
          <p className="muted" style={{ marginTop: 18 }}>{t("notif.loading")}</p>
        ) : rows.length === 0 ? (
          <div className="card" style={{ marginTop: 18 }}>
            <p style={{ margin: 0 }}>{page === 0 ? t("notif.empty") : t("notif.pageEnd")}</p>
            {page === 0 && <p className="muted" style={{ fontSize: 13.5, margin: "8px 0 0" }}>{t("notif.emptyHint")}</p>}
          </div>
        ) : (
          <div className="card" style={{ marginTop: 18, padding: 0, overflow: "hidden" }}>
            {rows.map((row, index) => {
              const when = relativeParts(row.created_at);
              const routable = routeForType(row.type, isBrand) !== null;
              return (
                <button
                  key={row.id}
                  type="button"
                  onClick={() => openRow(row)}
                  title={routable ? t("notif.opensScreen") : undefined}
                  style={{
                    display: "block", width: "100%", textAlign: "left", cursor: "pointer",
                    background: row.is_read ? "transparent" : "var(--surface-2)",
                    border: "none", borderTop: index === 0 ? "none" : "1px solid var(--line)",
                    padding: "12px 16px", fontFamily: "var(--font-body)"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <span aria-hidden="true" title={t("notif.unreadMark")}
                      style={{
                        width: 8, height: 8, borderRadius: "50%", marginTop: 6, flexShrink: 0,
                        background: row.is_read ? "transparent" : "var(--indigo)"
                      }} />
                    <span style={{ minWidth: 0, flex: 1 }}>
                      <span style={{ display: "block", fontSize: 14, fontWeight: row.is_read ? 400 : 600 }}>
                        {row.message}
                      </span>
                      <span className="muted" style={{ display: "block", fontSize: 12, marginTop: 3 }}>
                        {t(when.key, { n: when.n })}
                      </span>
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-ghost" disabled={page === 0 || loading}
            onClick={() => setPage((p) => Math.max(0, p - 1))}>
            {t("notif.newer")}
          </button>
          <span className="muted" style={{ fontSize: 13 }}>{t("notif.page", { n: page + 1 })}</span>
          <button type="button" className="btn btn-ghost" disabled={!hasMore || loading}
            onClick={() => setPage((p) => p + 1)}>
            {t("notif.older")}
          </button>
        </div>
      </div>
    </Layout>
  );
}
