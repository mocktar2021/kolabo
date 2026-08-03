import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { getStoredRole, isBusinessLike, useAuth } from "../lib/auth";
import {
  PANEL_LIMIT,
  notificationBody,
  relativeParts,
  targetFor,
  type AppNotification,
  type MarkAllRead,
  type UnreadCount
} from "../lib/notifications";

/* The bell, and the panel behind it.

   WHY IT EXISTS AT ALL. Notifications have been written to the database since
   Epic D — every invitation, proposal, contract, message, escrow movement and
   dispute writes one — and until now nothing in the web app displayed a
   single one of them. They were delivered by email and were invisible inside
   the product that raised them.

   THE BADGE IS FETCHED ON NAVIGATION AND NEVER POLLED, exactly like the
   messages and disputes badges beside it. Layout mounts on every screen of
   the app, so a mount effect already runs once per navigation; a timer here
   would hit /notifications/unread-count from every screen for as long as the
   tab stays open, to shave a few minutes off a number the panel refreshes the
   instant somebody opens it. location.pathname is in the dependency list
   rather than left implicit, so the refresh is a stated rule instead of an
   accident of how the router happens to remount this tree today.

   THE COUNT AND THE LIST ARE TWO REQUESTS, and that is the server's design
   rather than a client oversight: the list is capped at a page, so a badge
   counted from it would stop rising past the cap and quietly lie to anybody
   with more unread rows than a page holds. The count is a cheap COUNT and is
   the only thing asked for while the panel is shut.

   Zero renders no badge — a grey "0" is noise on every page of the app, which
   is the same call CartIndicator and MessagesIndicator make. */
export function NotificationsBell() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const isBrand = isBusinessLike(getStoredRole());

  useEffect(() => {
    if (!token) return;
    let live = true;
    api<UnreadCount>("/notifications/unread-count", { token })
      .then((res) => { if (live) setUnread(res.unread); })
      // A nav badge is not worth an error state. Silence leaves the rest of
      // the navigation working.
      .catch(() => undefined);
    return () => { live = false; };
  }, [token, location.pathname]);

  /* The rows are fetched when the panel opens and not before: most
     navigations never open it, and a screenful of notification text on every
     page load is a request nobody reads.

     The trailing slash is deliberate. The list route is declared as
     @router.get("/") under the /notifications prefix, so the path really is
     "/notifications/"; asking without it earns a 307 that the browser follows
     for no reason. */
  useEffect(() => {
    if (!open || !token) return;
    let live = true;
    setLoading(true);
    setFailed(false);
    api<AppNotification[]>(`/notifications/?limit=${PANEL_LIMIT}&offset=0`, { token })
      .then((res) => { if (live) setRows(res); })
      .catch(() => { if (live) { setRows([]); setFailed(true); } })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [open, token]);

  // Closes on an outside click and on Escape, the same way the account menu
  // does. Escape returns focus to the control that opened the panel, without
  // which a keyboard user is left at the top of the document with no idea
  // where the menu went.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  /* Opening one row: it is read, and then it goes wherever its link or TYPE
     leads — the backend's deep link when the row carries one, the type→screen
     fallback otherwise. targetFor argues that at length.

     The badge and the row are updated before the request rather than after
     it. Marking read is idempotent server-side and the worst case is a badge
     that is one too low until the next navigation refetches it, which is a
     far better failure than a panel that does nothing for a round trip. */
  function openRow(row: AppNotification) {
    setOpen(false);
    if (!row.is_read) {
      setRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, is_read: true } : r)));
      setUnread((n) => Math.max(0, n - 1));
      api(`/notifications/${row.id}/read`, { method: "POST", token }).catch(() => undefined);
    }
    const to = targetFor(row, isBrand);
    if (to) navigate(to);
  }

  /* One request rather than one per row. Somebody returning after a week has
     dozens, and clearing a badge should not cost dozens of round trips — the
     endpoint exists for exactly this and answers with how many rows it
     touched. */
  function markAll() {
    setRows((prev) => prev.map((r) => ({ ...r, is_read: true })));
    setUnread(0);
    api<MarkAllRead>("/notifications/read-all", { method: "POST", token }).catch(() => undefined);
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        type="button"
        ref={triggerRef}
        className="btn btn-ghost"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("notif.navAria", { n: unread })}
        onClick={() => setOpen((o) => !o)}
        style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 8.4a6 6 0 1 0-12 0c0 6-2.4 7.2-2.4 7.2h16.8S18 14.4 18 8.4" />
          <path d="M13.7 19.2a2 2 0 0 1-3.4 0" />
        </svg>
        {unread > 0 && (
          <span style={{ fontSize: 12, fontWeight: 700, color: "#fff", background: "var(--indigo)", borderRadius: 999, padding: "1px 7px" }}>
            {/* Past three digits the badge stops being a number and starts
                being a layout problem. */}
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="menu-panel" role="menu" style={{ left: "auto", right: 0, width: 330, maxWidth: "92vw" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, padding: "4px 12px 8px" }}>
            <strong style={{ fontFamily: "var(--font-display)", fontSize: 14.5 }}>{t("notif.panelTitle")}</strong>
            {/* Offered only when it would do something. A live "tout marquer
                comme lu" over an already-clear bell is a button that answers
                nothing. */}
            <button type="button" className="pp-see-more" disabled={unread === 0} onClick={markAll}
              style={{ fontSize: 12.5, opacity: unread === 0 ? 0.45 : 1, cursor: unread === 0 ? "default" : "pointer" }}>
              {t("notif.markAll")}
            </button>
          </div>

          {loading ? (
            <p className="muted" style={{ fontSize: 13.5, margin: 0, padding: "6px 12px 10px" }}>{t("notif.loading")}</p>
          ) : failed ? (
            <p className="muted" style={{ fontSize: 13.5, margin: 0, padding: "6px 12px 10px" }}>{t("notif.loadFailed")}</p>
          ) : rows.length === 0 ? (
            <p className="muted" style={{ fontSize: 13.5, margin: 0, padding: "6px 12px 10px" }}>{t("notif.empty")}</p>
          ) : (
            rows.map((row) => {
              const when = relativeParts(row.created_at);
              const routable = targetFor(row, isBrand) !== null;
              return (
                <button
                  key={row.id}
                  type="button"
                  role="menuitem"
                  onClick={() => openRow(row)}
                  title={routable ? t("notif.opensScreen") : undefined}
                  style={{
                    display: "block", width: "100%", textAlign: "left", cursor: "pointer",
                    background: row.is_read ? "transparent" : "var(--surface-2)",
                    border: "none", borderTop: "1px solid var(--line)", padding: "9px 12px",
                    fontFamily: "var(--font-body)"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                    {/* The unread marker is a dot AND a background, because a
                        dot alone is invisible to anybody who cannot pick it
                        out; the title attribute names it for a screen
                        reader. */}
                    <span aria-hidden="true" title={t("notif.unreadMark")}
                      style={{
                        width: 7, height: 7, borderRadius: "50%", marginTop: 6, flexShrink: 0,
                        background: row.is_read ? "transparent" : "var(--indigo)"
                      }} />
                    <span style={{ minWidth: 0 }}>
                      <span style={{ display: "block", fontSize: 13.5, fontWeight: row.is_read ? 400 : 600, whiteSpace: "normal" }}>
                        {notificationBody(row, t)}
                      </span>
                      <span className="muted" style={{ display: "block", fontSize: 11.5, marginTop: 2 }}>
                        {t(when.key, { n: when.n })}
                      </span>
                    </span>
                  </div>
                </button>
              );
            })
          )}

          <div style={{ borderTop: "1px solid var(--line)", padding: "9px 12px 3px" }}>
            <Link to="/notifications" onClick={() => setOpen(false)} style={{ fontSize: 13, fontWeight: 600 }}>
              {t("notif.seeAll")}
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
