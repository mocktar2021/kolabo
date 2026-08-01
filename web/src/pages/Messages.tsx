import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorChip } from "../components/CreatorChip";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { parseApiDate } from "../lib/orders";
import type { Message, MessageThread } from "../lib/types";

/* Mirrors the body cap on MessageIn in
   backend/app/modules/messaging/schemas.py. */
const BODY_MAX_LENGTH = 4000;

/* THE PRODUCT RULE THIS WHOLE SCREEN RESTS ON.

   A thread exists on a campaign only once a CONTRACT exists on it between the
   two people in it. Not an invitation, not a proposal — a contract. The
   inbox is therefore built server-side from contracts rather than from
   messages, which is why a conversation nobody has written in yet still shows
   up: a contract just signed is precisely when somebody needs to start one.

   Open messaging between any brand and any creator is a lead channel, and a
   lead channel is a thing people mine: a hundred identical "hi, what are your
   rates" messages, most answered by nobody, until both sides learn the inbox
   is noise and stop opening it. The creators who suffer most are the ones with
   the biggest audiences, which is to say the ones the marketplace most needs
   to keep. And a conversation that starts before there is a deal is a
   conversation that leaves for WhatsApp the moment it gets specific — and a
   deal agreed there has no contract, no escrow and no recourse for either
   side.

   After a contract it is a different product entirely: two people have agreed
   terms and now have work to do together — shot lists, delivery dates,
   revisions, "the light was wrong, can I reshoot Thursday". That is also the
   evidence trail a dispute reads, which is why read_at is a timestamp and not
   a flag. All of which is what the empty state says out loud instead of
   apologising for being empty. */
export default function MessagesPage() {
  const { t } = useTranslation();
  const { token, userId, isAuthenticated } = useAuth();
  const [params] = useSearchParams();

  const [threads, setThreads] = useState<MessageThread[]>([]);
  const [active, setActive] = useState<MessageThread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* "il y a 2 h", off a naive UTC string. parseApiDate is what stops the
     browser reading "2026-07-31T09:12:00" as local time — the same helper the
     48 h order clock uses, and for the same reason: left alone it invents or
     destroys hours depending on where the reader is sitting. Computed on
     render rather than on a timer; nothing here is worth a ticking clock. */
  const relative = useCallback(
    (iso: string): string => {
      const minutes = Math.floor((Date.now() - parseApiDate(iso)) / 60000);
      if (minutes < 1) return t("msg.justNow");
      if (minutes < 60) return t("msg.minutesAgo", { n: minutes });
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return t("msg.hoursAgo", { n: hours });
      return t("msg.daysAgo", { n: Math.floor(hours / 24) });
    },
    [t]
  );

  const loadThreads = useCallback(async () => {
    try {
      setThreads(await api<MessageThread[]>("/messaging/threads", { token }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [token]);

  /* Opening a thread IS reading it: the endpoint stamps the caller's incoming
     messages read as it serves them, which is why there is no separate
     mark-as-read call and why the list is refetched afterwards — the unread
     badges on it have just changed underneath us. */
  const openThread = useCallback(
    async (thread: MessageThread) => {
      setActive(thread);
      setError(null);
      setDraft("");
      try {
        const rows = await api<Message[]>(
          `/messaging/campaigns/${thread.campaign_id}/messages?with_user_id=${encodeURIComponent(thread.counterparty_user_id)}`,
          { token }
        );
        setMessages(rows);
        await loadThreads();
      } catch (e) {
        // A 403 here means the contract that opened this thread is gone, which
        // the server explains in its own words. Shown as-is.
        setMessages([]);
        setError(e instanceof Error ? e.message : "Error");
      }
    },
    [token, loadThreads]
  );

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  /* Arriving from a contract page, which links with the campaign and the
     other party in the query string. Matched against the loaded list rather
     than trusted blindly: the thread carries the counterparty's name and
     unread count, and a hand-typed URL for a contract that does not exist
     should land on the inbox rather than on a broken conversation. */
  useEffect(() => {
    if (active || threads.length === 0) return;
    const campaign = params.get("campaign");
    const withUser = params.get("with");
    if (!campaign || !withUser) return;
    const found = threads.find(
      (th) => th.campaign_id === campaign && th.counterparty_user_id === withUser
    );
    if (found) openThread(found);
  }, [threads, active, params, openThread]);

  async function send() {
    const body = draft.trim();
    if (!body || !active) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/messaging/campaigns/${active.campaign_id}/messages`, {
        method: "POST",
        token,
        body: { to_user_id: active.counterparty_user_id, body }
      });
      // Refetched rather than appended locally: the server assigns the id and
      // the timestamp, and a message that exists only on screen is the one
      // that turns out never to have been sent.
      await openThread(active);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  /* The counterparty as CreatorChip renders anybody else in this app. The
     fallback is neutral rather than the chip's own "Créateur sans nom":
     half of these rows are brands, and calling a company an unnamed creator
     would be wrong in a way the reader cannot correct. */
  const chipFor = (thread: MessageThread) => ({
    display_name: thread.counterparty_name || t("msg.unknownParty"),
    avatar_url: thread.counterparty_avatar_url,
    top_platform: null,
    top_follower_count: null
  });

  return (
    <Layout>
      <div className="container page">
        <h1 style={{ margin: 0 }}>{t("msg.title")}</h1>
        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {loading ? (
          <p className="muted" style={{ marginTop: 18 }}>{t("discover.loading")}</p>
        ) : threads.length === 0 ? (
          <div className="card" style={{ marginTop: 18 }}>
            <p style={{ margin: 0 }}>{t("msg.empty")}</p>
            <p className="muted" style={{ fontSize: 13.5, margin: "8px 0 0" }}>{t("msg.emptyHint")}</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16, alignItems: "start", marginTop: 18 }}>
            <div className="card" style={{ padding: 0, overflow: "hidden" }}>
              {threads.map((thread) => {
                const isActive =
                  active?.campaign_id === thread.campaign_id &&
                  active?.counterparty_user_id === thread.counterparty_user_id;
                return (
                  <button
                    key={thread.contract_id}
                    type="button"
                    onClick={() => openThread(thread)}
                    style={{
                      display: "block", width: "100%", textAlign: "left", cursor: "pointer",
                      background: isActive ? "var(--surface-2)" : "transparent",
                      border: "none", borderBottom: "1px solid var(--line)", padding: "12px 14px"
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                      <CreatorChip creator={chipFor(thread)} />
                      {/* Unread is always about what was sent TO the reader;
                          their own outgoing messages are never unread to
                          them. Zero renders nothing at all. */}
                      {thread.unread_count > 0 && (
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#fff", background: "var(--indigo)", borderRadius: 999, padding: "1px 8px" }}>
                          {thread.unread_count}
                        </span>
                      )}
                    </div>
                    {thread.campaign_title && (
                      <div className="muted" style={{ fontSize: 12.5, marginTop: 6 }}>{thread.campaign_title}</div>
                    )}
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginTop: 4 }}>
                      <span className="muted clamp-2" style={{ fontSize: 13, minWidth: 0 }}>
                        {thread.last_message ?? t("msg.noMessages")}
                      </span>
                      {thread.last_message_at && (
                        <span className="muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                          {relative(thread.last_message_at)}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="card">
              {!active ? (
                <p className="muted" style={{ margin: 0 }}>{t("msg.pick")}</p>
              ) : (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <CreatorChip creator={chipFor(active)} />
                    <Link to={`/contracts/${active.contract_id}`} style={{ fontSize: 13.5, fontWeight: 600 }}>
                      {t("contract.title")}
                    </Link>
                  </div>

                  <div style={{ display: "grid", gap: 8, margin: "14px 0" }}>
                    {messages.length === 0 ? (
                      <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("msg.noMessages")}</p>
                    ) : (
                      messages.map((m) => {
                        const mine = m.sender_user_id === userId;
                        return (
                          <div
                            key={m.id}
                            style={{
                              justifySelf: mine ? "end" : "start",
                              maxWidth: "85%",
                              background: mine ? "var(--surface-2)" : "var(--surface)",
                              border: "1px solid var(--line)",
                              borderRadius: "var(--radius-sm)",
                              padding: "8px 12px"
                            }}
                          >
                            <div style={{ fontSize: 12, fontWeight: 700 }}>
                              {mine ? t("msg.you") : active.counterparty_name || t("msg.unknownParty")}
                            </div>
                            <p style={{ fontSize: 14, margin: "2px 0 0", whiteSpace: "pre-wrap" }}>{m.body}</p>
                            <div className="muted" style={{ fontSize: 11.5, marginTop: 4 }}>{relative(m.created_at)}</div>
                          </div>
                        );
                      })
                    )}
                  </div>

                  <textarea
                    className="input"
                    rows={3}
                    maxLength={BODY_MAX_LENGTH}
                    style={{ resize: "vertical" }}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder={t("msg.placeholder")}
                  />
                  <button className="btn btn-primary" style={{ marginTop: 10 }} disabled={busy || !draft.trim()} onClick={send}>
                    {busy ? t("auth.working") : t("msg.send")}
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
