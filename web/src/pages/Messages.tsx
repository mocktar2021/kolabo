import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorChip } from "../components/CreatorChip";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { parseApiDate } from "../lib/orders";
import type { Message, MessageThread } from "../lib/types";

/* Mirrors the body cap on DirectMessageIn in
   backend/app/modules/messaging/schemas.py. */
const BODY_MAX_LENGTH = 4000;

/* THE PRODUCT RULE THIS WHOLE SCREEN RESTS ON.

   A thread exists between two people only once a CONTRACT exists between
   them. Not an invitation, not a proposal — a contract. The inbox is
   therefore built server-side from contracts rather than from messages, which
   is why a conversation nobody has written in yet still shows up: a contract
   just signed is precisely when somebody needs to start one.

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
   apologising for being empty.

   AND THE ROW IS A PERSON, NOT A JOB. This screen used to list one thread per
   CONTRACT, so a creator on their third campaign with the same brand had
   three inboxes with the same name on them: three places to look for what was
   said about a deadline last time, and a history that fragmented further with
   every job they won. Exactly backwards — a relationship is worth more each
   time it repeats, and the product was chopping it up in response, which made
   the strongest repeat business look like the most confusing inbox. The
   contracts are now an attribute of the relationship: a count on the row and
   a list in the header. */
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
      setError(errorText(e, t));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  /* Opening a thread IS reading it: the endpoint stamps the caller's incoming
     messages read as it serves them, which is why there is no separate
     mark-as-read call and why the list is refetched afterwards — the unread
     badges on it have just changed underneath us.

     Addressed to the PERSON. The per-campaign endpoint still exists and still
     works, but it answers one job's slice of a conversation, and a question
     asked during the second job and answered during the third only reads as a
     conversation here. */
  const openThread = useCallback(
    async (thread: MessageThread) => {
      setActive(thread);
      setError(null);
      setDraft("");
      try {
        const rows = await api<Message[]>(
          `/messaging/with/${encodeURIComponent(thread.counterparty_user_id)}`,
          { token }
        );
        setMessages(rows);
        await loadThreads();
      } catch (e) {
        // A 403 here means every contract with this person is gone. Messaging
        // is not converted to error codes yet, so that one still arrives as
        // English prose and errorText passes it through unchanged; the contact
        // guard's refusal, which IS converted, arrives in the reader's own
        // language.
        setMessages([]);
        setError(errorText(e, t));
      }
    },
    [token, loadThreads, t]
  );

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  /* Arriving from a contract page, which links with the campaign and the
     other party in the query string.

     Only `with` is read now: a row is a person, so the counterparty alone
     identifies it and a campaign cannot narrow it further. The parameter is
     still SENT by the contract page and is accepted and ignored rather than
     required, so a link or a bookmark written against the per-contract shape
     still lands on the right conversation.

     Matched against the loaded list rather than trusted blindly: the thread
     carries the counterparty's name, contracts and unread count, and a
     hand-typed URL for somebody the reader has no contract with should land
     on the inbox rather than on a broken conversation. */
  useEffect(() => {
    if (active || threads.length === 0) return;
    const withUser = params.get("with");
    if (!withUser) return;
    const found = threads.find((th) => th.counterparty_user_id === withUser);
    if (found) openThread(found);
  }, [threads, active, params, openThread]);

  async function send() {
    const body = draft.trim();
    if (!body || !active) return;
    setBusy(true);
    setError(null);
    try {
      /* Posted to the person, not to a campaign. The server stamps the
         message with the most recent shared contract's campaign, which keeps
         every message's provenance intact — which job a conversation was
         about is what a dispute reads — without the client having to choose a
         campaign the two of them are "currently" on.

         No to_user_id in the body: the recipient is in the path, and two
         places to say who a message is for is one place to get it wrong. */
      await api(`/messaging/with/${encodeURIComponent(active.counterparty_user_id)}`, {
        method: "POST",
        token,
        body: { body }
      });
      // Refetched rather than appended locally: the server assigns the id and
      // the timestamp, and a message that exists only on screen is the one
      // that turns out never to have been sent.
      await openThread(active);
    } catch (e) {
      setError(errorText(e, t));
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
                const isActive = active?.counterparty_user_id === thread.counterparty_user_id;
                return (
                  <button
                    /* Keyed by the PERSON. It used to be the contract id, which
                       is what produced four rows with the same name on them
                       for four jobs with the same brand. */
                    key={thread.counterparty_user_id}
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
                      {/* Unread is always about what was sent TO the reader,
                          and now across the whole relationship rather than one
                          job: an unanswered question is unanswered whichever
                          contract it was asked under. Zero renders nothing. */}
                      {thread.unread_count > 0 && (
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#fff", background: "var(--indigo)", borderRadius: 999, padding: "1px 8px" }}>
                          {thread.unread_count}
                        </span>
                      )}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginTop: 6 }}>
                      {/* The job they are currently on names the row; how many
                          they have done together is the fact worth adding, and
                          only once there is more than one — "1 contrat" on
                          every row of the list is noise. */}
                      {thread.campaign_title && (
                        <span className="muted" style={{ fontSize: 12.5 }}>{thread.campaign_title}</span>
                      )}
                      {thread.contract_count > 1 && (
                        <span style={{ fontSize: 11.5, fontWeight: 600, padding: "2px 8px", borderRadius: 999, background: "var(--surface-2)", color: "var(--muted)", whiteSpace: "nowrap" }}>
                          {t("msg.contractsCount", { n: thread.contract_count })}
                        </span>
                      )}
                    </div>
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
                    <ContractsMenu thread={active} />
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

/* The jobs behind one relationship, in the conversation header.

   One contract renders as the plain link it always was — a dropdown holding a
   single item is a control that exists to be opened and disappoint. Several
   render as a toggle over the list, newest first, because that is the whole
   point of collapsing the rows: the conversation is one thing, and the four
   contracts under it are still individually reachable.

   NAMED BY POSITION, oldest first, so a new contract never renumbers the ones
   above it. Only the newest one's campaign title comes down on the thread
   payload, and fetching a title for each of the others would be a request per
   contract to decorate a link somebody opened this menu to click. The newest
   is marked as the current job, which is the one thing that actually
   distinguishes them at a glance. */
function ContractsMenu({ thread }: { thread: MessageThread }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on any click outside, the same way the marketing features menu
  // does: a document listener needs no new dependency and survives clicks on
  // elements that never receive focus.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  /* Falls back to the single contract the row has always carried, so a thread
     served by an older API build (contract_ids absent, contract_id present)
     still renders a working link rather than an empty menu. */
  const ids = thread.contract_ids && thread.contract_ids.length > 0
    ? thread.contract_ids
    : [thread.contract_id];

  if (ids.length === 1) {
    return (
      <Link to={`/contracts/${ids[0]}`} style={{ fontSize: 13.5, fontWeight: 600 }}>
        {t("contract.title")}
      </Link>
    );
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button type="button" className="btn btn-ghost" style={{ padding: "5px 10px", fontSize: 13 }}
        aria-haspopup="true" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {t("msg.contracts")} ({ids.length}) ▾
      </button>
      {open && (
        <div className="menu-panel" role="menu" style={{ right: 0 }}>
          {ids.map((contractId, index) => (
            <Link key={contractId} className="menu-item" role="menuitem"
              to={`/contracts/${contractId}`} onClick={() => setOpen(false)}>
              <span className="t">{t("msg.contractN", { n: ids.length - index })}</span>
              {/* The list arrives newest first, so index 0 is the job the two
                  of them are on right now — and the only one whose campaign
                  title the thread payload carries. */}
              {index === 0 && (
                <span className="d">
                  {thread.campaign_title
                    ? `${thread.campaign_title} · ${t("msg.contractCurrent")}`
                    : t("msg.contractCurrent")}
                </span>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
