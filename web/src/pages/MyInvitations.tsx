import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { LicenceTerms } from "../components/LicenceTerms";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { CURRENCIES } from "../lib/campaignOptions";
import { licenceRowFor } from "../lib/licence";
import { directOrderOf, orderTimeLeft, parseApiDate } from "../lib/orders";
import { PLATFORM_LABELS } from "../lib/platforms";
import { ListFilter, type FilterOption } from "../components/ListFilter";
import type { Contract, InvitationWithCampaign, Proposal } from "../lib/types";

/* Mirrors MAX_NOTE_LENGTH in backend/app/modules/campaigns/schemas.py. Enforced
   here too so the limit is hit as a full textarea rather than as a 422 after
   the creator has finished typing. */
const NOTE_MAX_LENGTH = 2000;

/* THE CAMPAIGN STATUSES THAT TAKE NO MORE ANSWERS.

   Campaign.status is exactly draft, published, cancelled and completed, and
   the last two are the terminal pair: one was called off, the other ran to
   the end and was paid out. submit_proposal answers 400 campaign_not_open to
   both, so both have to close this card's forms.

   A single test against "cancelled" covered half of that and left a finished
   brief showing an invited creator the whole blank rate, currency, days and
   note form with a live Send button on it, which could only ever earn that
   refusal. A set rather than a chain of comparisons because there is one
   question here, asked in three places on this card, and the next status that
   ends a campaign should join it in one edit. */
const CLOSED_CAMPAIGN_STATUSES = new Set(["cancelled", "completed"]);

/* "Envoyé il y a 2 h" for one version of a chain, as a key and a number
   rather than as a finished string — the shape lib/notifications.ts already
   uses for the bell, so the caller keeps its own `t` and this stays a pure
   function of the timestamp.

   parseApiDate is what stops the browser reading "2026-07-31T09:12:00" as
   local time: the same helper the 48 h order clock uses, and for the same
   reason — left alone it invents or destroys hours depending on where the
   creator is sitting. Computed on render rather than on a timer; a
   negotiation round is not worth a ticking clock. */
function sentParts(iso: string): { key: string; n: number } {
  const minutes = Math.floor((Date.now() - parseApiDate(iso)) / 60000);
  if (minutes < 1) return { key: "invitation.sentJustNow", n: 0 };
  if (minutes < 60) return { key: "invitation.sentMinutesAgo", n: minutes };
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return { key: "invitation.sentHoursAgo", n: hours };
  return { key: "invitation.sentDaysAgo", n: Math.floor(hours / 24) };
}

function ProposalForm({ campaignId, onDone }: { campaignId: string; onDone: () => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rate, setRate] = useState("");
  const [currency, setCurrency] = useState("XOF");
  const [days, setDays] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit() {
    if (!rate || !days) return;
    setBusy(true);
    setError(null);
    try {
      /* The note travels with the offer rather than in a message beside it, so
         the terms and the reasoning for them stay in one record — the same
         record the business answers and the contract is eventually written
         from. Omitted entirely when empty: a creator who wants to send bare
         numbers still can. */
      const trimmed = note.trim();
      await api(`/campaigns/${campaignId}/proposals`, {
        method: "POST",
        token,
        body: {
          rate_amount: Number(rate),
          rate_currency: currency,
          timeline_days: Number(days),
          ...(trimmed ? { note: trimmed } : {})
        }
      });
      setDone(true);
      onDone();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  if (done) return <div className="alert alert-success" style={{ marginBottom: 0 }}>{t("invitation.proposalSent")}</div>;

  return (
    <div>
      {error && <div className="alert alert-error">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 90px 1fr", gap: 8, alignItems: "end" }}>
        <div>
          <label className="label">{t("invitation.rate")}</label>
          <input className="input" inputMode="numeric" value={rate} onChange={(e) => setRate(e.target.value.replace(/\D/g, ""))} placeholder="40000" />
        </div>
        <div>
          <label className="label">{t("campaign.currency")}</label>
          <select className="select" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="label">{t("invitation.days")}</label>
          <input className="input" inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))} placeholder="7" />
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <label className="label">{t("invitation.note")}</label>
        <textarea
          className="input"
          rows={3}
          maxLength={NOTE_MAX_LENGTH}
          style={{ resize: "vertical" }}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t("invitation.notePlaceholder")}
        />
      </div>
      <button className="btn btn-primary" style={{ marginTop: 12 }} disabled={busy || !rate || !days} onClick={submit}>{t("invitation.send")}</button>
    </div>
  );
}

/* The creator's answer with different numbers on it.

   There is no creator-side counter endpoint and there does not need to be
   one: the next version in the chain IS the counter, so this posts to the
   same submit path a brief's first proposal takes.

   On a direct order it keeps the 48 h clock. submit_proposal carries
   expires_at forward from the version it answers, deliberately — a countered
   order is still the same order, and restarting the window on every round
   would let one chain run forever while the buyer waits.

   Prefilled with the terms on the table rather than blank: the creator is
   almost always changing one of the two numbers, and the endpoint needs both
   regardless.

   NOTHING HERE COUNTERS THE LICENCE, and that is the backend's shape rather
   than an omission. A proposal version is a rate, a currency and a timeline;
   the licence rides on the campaign, which is the brand's to state. A creator
   who finds option 2 priced as option 1 counters with a higher number, which
   is exactly the conversation the panel above this form exists to start. */
function CounterForm({ campaignId, live, isOrder, onSent }: {
  campaignId: string;
  live: Proposal;
  isOrder: boolean;
  onSent: () => void;
}) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rate, setRate] = useState(String(live.rate_amount));
  const [days, setDays] = useState(String(live.timeline_days));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!rate || !days) return;
    setBusy(true);
    setError(null);
    try {
      const trimmed = note.trim();
      await api(`/campaigns/${campaignId}/proposals`, {
        method: "POST",
        token,
        body: {
          rate_amount: Number(rate),
          /* Not counterable: a chain is priced in one currency or it is two
             negotiations pretending to be one. The business reply endpoint
             refuses to change it for exactly the same reason, so the counter
             repeats the currency already on the table. */
          rate_currency: live.rate_currency,
          timeline_days: Number(days),
          ...(trimmed ? { note: trimmed } : {})
        }
      });
      onSent();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 12, background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "var(--radius-sm)", padding: 14 }}>
      {error && <div className="alert alert-error">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <div>
          <label className="label">{t("invitation.rate")} ({live.rate_currency})</label>
          <input className="input" inputMode="numeric" value={rate}
            onChange={(e) => setRate(e.target.value.replace(/\D/g, ""))} />
        </div>
        <div>
          <label className="label">{t("invitation.days")}</label>
          <input className="input" inputMode="numeric" value={days}
            onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))} />
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <label className="label">{t("invitation.note")}</label>
        <textarea
          className="input"
          rows={3}
          maxLength={NOTE_MAX_LENGTH}
          style={{ resize: "vertical" }}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t("invitation.notePlaceholder")}
        />
      </div>
      {isOrder && <p className="hint">{t("invitation.counterHint")}</p>}
      <button className="btn btn-primary" style={{ marginTop: 12 }} disabled={busy || !rate || !days} onClick={submit}>
        {t("invitation.counterSend")}
      </button>
    </div>
  );
}

/* Whose turn it is, and what the other side actually said.

   A business could already answer a proposal, but the answer landed in a
   notification and nowhere else: the creator was shown a blank proposal form
   and had no way to read the counter they were meant to be answering. A
   negotiation with one side unable to read it is not a negotiation, and the
   place it moves to instead is WhatsApp.

   The turn is DERIVED from the live version's author_role rather than stored.
   author_role already answers the question — one of the two sides wrote the
   last word and there is exactly one of those — so a "waiting_on" column
   would be a second copy of that fact, written by hand at every step. The
   first counter that forgot to update it would confidently tell a creator to
   wait on a reply they were themselves holding. Deriving cannot drift.

   What the creator may DO is not symmetric, and the asymmetry is the
   backend's rather than a styling choice:

     - Accept exists only on a direct order whose live version is the brand's.
       A brief's proposals are accepted by the BUSINESS through the contracts
       path — campaigns/orders.py refuses a non-direct campaign outright — and
       accepting one's own counter is a 400 ("This is your own counter-offer.
       The brand has to accept it."). A button that exists only to be refused
       is worse than no button, so it is not offered at all.

     - Decline stays on an open order whichever side holds the live version.
       Withdrawing an offer you made is a different act from signing one, and
       the backend allows it on purpose: a creator who changed their mind
       should be able to close the order rather than leave the buyer waiting
       on a number nobody intends to honour.

     - Withdraw is the BRIEF-side mirror of decline, and the two must not be
       confused. See withdrawProposal below.

     - Counter is the answer available on both kinds of row, and it is simply
       the next version in the chain. */
function Negotiation({ campaignId, live, history, isOrder, readOnly = false, onDone }: {
  campaignId: string;
  live: Proposal;
  /* Every version of this chain, oldest first, with the live one last. Empty
     when the row came from an API that predates proposal_history — see
     `versions` below, which falls back to the live version alone. */
  history: Proposal[];
  isOrder: boolean;
  /* True when the campaign underneath has ended, cancelled or completed: the
     thread stays readable — it is the record of what was offered — but every
     action goes, because the backend would refuse it with campaign_not_open
     and a button that only ever earns a refusal is a trap. */
  readOnly?: boolean;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [counterOpen, setCounterOpen] = useState(false);
  /* One inline confirmation slot for the two irreversible answers on this
     card. Never window.confirm: the sentence that makes each of them an easy
     decision — nobody is charged, nothing is a refusal — does not fit in a
     browser dialog and cannot be translated in one. */
  const [confirming, setConfirming] = useState<"decline" | "withdraw" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const left = live.expires_at ? orderTimeLeft(live.expires_at) : null;
  // Only orders run on a clock, so only orders can lapse. A brief's proposal
  // has no expires_at and stays answerable.
  const expired = isOrder && left === null;
  // Superseded, accepted or declined: already answered, so the row is history.
  const open = live.status === "submitted" && !readOnly;
  // The brand wrote the live version, so the ball is in the creator's court.
  const theirMove = live.author_role === "business";
  /* The thread to draw. An empty history means the payload came from a
     backend that does not send one yet, and the honest answer there is the
     single version we do have rather than a blank panel. */
  const versions = history.length > 0 ? history : [live];

  /* WHEN THE CREATOR MAY PULL THEIR OWN OFFER BACK, and it is narrower than
     it looks:

       - A BRIEF ONLY. A direct order is deliberately excluded and must not
         get this button. An order is closed by DECLINING it, which does three
         things withdrawing does not: it cancels the hidden campaign, moves
         the invitation to declined, and tells the buyer they were not
         charged. withdraw_proposal refuses an order with a 400 pointing at
         the decline endpoint rather than doing half the job — so offering it
         here would be offering a button whose only outcome is a refusal, next
         to the Refuser button that actually works.

       - THEIR OWN LIVE VERSION. If the brand wrote the last word, the
         creator's own version was superseded when they answered it and there
         is nothing of theirs left on the table; the endpoint answers 400
         ("not the live offer"). author_role is what tells the two apart.

       - AND STILL OPEN. Accepted, rejected or superseded rows are history. */
  const withdrawable = !isOrder && open && !theirMove;

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      /* Accepting is what creates the contract — the endpoint returns it, and
         signing is the next thing both sides have to do, so that is where the
         creator goes. Money still has not moved: escrow is funded by the buyer
         after both signatures.

         THE LICENCE IS ON SCREEN ABOVE THIS BUTTON, which is the point of
         putting it on the card at all. Accepting an order generates the
         contract, and article 10 of that contract carries whatever the brand
         stated: a creator who has not read it has agreed to it anyway. The
         generation also refuses with contract_licence_terms_missing when
         nothing was stated, and errorText has that sentence in both
         languages. */
      const contract = await api<Contract>(`/campaigns/orders/${live.id}/accept`, { method: "POST", token });
      navigate(`/contracts/${contract.id}`);
    } catch (e) {
      // Covers the late click. "This order has expired." arrives as a 400
      // carrying no code yet, so errorText falls back to the server's own
      // sentence — and starts showing a translated one the day orders.py
      // sends a code for it.
      setError(errorText(e, t));
      setBusy(false);
    }
  }

  async function decline() {
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/orders/${live.id}/decline`, { method: "POST", token });
      // Reload rather than patch locally: the invitation status, the campaign
      // status and the proposal status all move together server-side.
      onDone();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  /* Taking a live offer back off the table on a brief.

     WITHDRAWN IS NOT DECLINED, and the distinction is the whole reason this
     endpoint exists separately: declining records that somebody said no, and
     nobody said no here. Putting a refusal on a record that never made one
     is the kind of small dishonesty that makes a reputation system
     worthless.

     The superseded version underneath is NOT revived, which the confirmation
     says out loud: every earlier version was withdrawn by its own author when
     they wrote the next one, and putting old terms back on the table would be
     the platform making an offer on somebody's behalf. */
  async function withdrawProposal() {
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/proposals/${live.id}/withdraw`, { method: "POST", token });
      onDone();
    } catch (e) {
      /* By CODE, which separates what the shared 400 ran together:
         `proposal_not_live` when the offer has already been superseded,
         `proposal_has_contract` when a contract was generated from it, and
         `proposal_is_direct_order` when the row belongs on the decline path
         instead. Each of the three sends the creator somewhere different, so
         each gets its own sentence. */
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ borderTop: "1px solid var(--line)", marginTop: 20, paddingTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span className="label" style={{ margin: 0 }}>{t("invitation.negotiationTitle")}</span>
        {open && (
          <span
            style={theirMove
              ? { fontSize: 12, fontWeight: 700, color: "#fff", background: "var(--teal-600)", padding: "3px 10px", borderRadius: 999 }
              : { fontSize: 12, fontWeight: 600, color: "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}
          >
            {theirMove ? t("invitation.turnYours") : t("invitation.turnBrand")}
          </span>
        )}
      </div>

      {/* The whole exchange, oldest first, laid out the way CampaignDetail's
          ProposalThread lays it out — author, terms, note, version, with the
          live one marked — so the two sides are reading the same negotiation
          in the same shape. The live version is last, and the controls below
          belong to it.

          Every round and not just the last: a counter is an answer to
          something, and a creator shown the answer without the question was
          being asked to price a conversation they could not read. */}
      <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
        {versions.map((v) => {
          const isLive = v.id === live.id;
          const fromBrand = v.author_role === "business";
          // Null only on a row written before created_at was serialised.
          const when = v.created_at ? sentParts(v.created_at) : null;
          return (
            <div
              key={v.id}
              style={{
                borderLeft: `3px solid ${isLive ? "var(--indigo)" : "var(--line)"}`,
                background: isLive ? "var(--surface-2)" : "transparent",
                borderRadius: "0 var(--radius-sm) var(--radius-sm) 0",
                padding: "8px 12px"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, fontSize: 12.5 }}>
                <span style={{ fontWeight: 700 }}>
                  {fromBrand ? t("campaign.authorBrand") : t("campaign.authorCreator")}
                </span>
                <span className="muted">
                  {isLive && <span style={{ color: "var(--indigo)", fontWeight: 600, marginRight: 8 }}>{t("campaign.currentOffer")}</span>}
                  v{v.version}
                </span>
              </div>
              <div style={{ fontSize: 14.5, fontWeight: isLive ? 700 : 500 }}>
                {v.rate_amount} {v.rate_currency} · {v.timeline_days} {t("campaign.daysShort")}
              </div>
              {v.note && (
                <p className="muted" style={{ fontSize: 13.5, margin: "4px 0 0", whiteSpace: "pre-wrap" }}>{v.note}</p>
              )}
              {when && (
                <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>{t(when.key, { n: when.n })}</p>
              )}
            </div>
          );
        })}
      </div>

      {/* The clock, stated in the unit that is still useful: hours while there
          is a day left, minutes in the last stretch. Orders only — a brief's
          proposal has nothing to count down. */}
      {isOrder && (
        <p className="muted" style={{ fontSize: 13, margin: "12px 0 0", fontWeight: expired ? 600 : 400 }}>
          {expired || left === null
            ? t("invitation.orderExpired")
            : left.unit === "hours"
              ? t("invitation.orderExpiresHours", { n: left.n })
              : t("invitation.orderExpiresMinutes", { n: left.n })}
        </p>
      )}

      {error && <div className="alert alert-error" style={{ marginTop: 12, marginBottom: 0 }}>{error}</div>}

      {open && (
        confirming === "decline" ? (
          <div style={{ marginTop: 14 }}>
            {/* Inline, not a window.confirm: the sentence that makes this an
                easy decision — no money has moved, so a no costs the brand
                nothing but the wait — does not fit in a browser dialog. */}
            <p className="muted" style={{ fontSize: 13.5, margin: "0 0 10px" }}>{t("invitation.orderDeclineConfirm")}</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-ghost" disabled={busy} onClick={decline}>{t("invitation.orderDeclineYes")}</button>
              <button className="btn btn-ghost" disabled={busy} onClick={() => setConfirming(null)}>{t("invitation.orderDeclineNo")}</button>
            </div>
          </div>
        ) : confirming === "withdraw" ? (
          <div style={{ marginTop: 14 }}>
            <p className="muted" style={{ fontSize: 13.5, margin: "0 0 10px" }}>{t("undo.proposalConfirm")}</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-ghost" disabled={busy} onClick={withdrawProposal}>{t("undo.proposalYes")}</button>
              <button className="btn btn-ghost" disabled={busy} onClick={() => { setConfirming(null); setError(null); }}>{t("undo.proposalNo")}</button>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
            {isOrder && theirMove && (
              <button className="btn btn-primary" disabled={busy || expired} onClick={accept}>{t("invitation.orderAccept")}</button>
            )}
            {isOrder && (
              <button className="btn btn-ghost" disabled={busy || expired} onClick={() => setConfirming("decline")}>{t("invitation.orderDecline")}</button>
            )}
            {/* Briefs only. An order gets Refuser above and nothing else — see
                withdrawable. */}
            {withdrawable && (
              <button className="btn btn-ghost" disabled={busy} onClick={() => { setConfirming("withdraw"); setError(null); }}>
                {t("undo.proposalWithdraw")}
              </button>
            )}
            {theirMove && !expired && (
              <button className="btn btn-ghost" disabled={busy} onClick={() => setCounterOpen((o) => !o)}>{t("invitation.counter")}</button>
            )}
          </div>
        )
      )}

      {counterOpen && open && theirMove && !expired && (
        <CounterForm
          campaignId={campaignId}
          live={live}
          isOrder={isOrder}
          onSent={() => { setCounterOpen(false); onDone(); }}
        />
      )}
    </div>
  );
}

/* One invitation, read top to bottom the way the decision is actually made:
   who is asking, what they want made, what they budgeted, by when — and only
   at the bottom, what the creator wants to be paid. Quoting a number before
   seeing the deliverables was guesswork.

   Two kinds of row share this card. A live proposal carrying expires_at means
   a brand bought a package or sent terms of its own and the offer is already
   on the table; anything else is a brief to price. Only direct orders run on a
   clock, which is what makes that field the test — see lib/orders.ts. */
function InvitationCard({ inv, onDone }: { inv: InvitationWithCampaign; onDone: () => void }) {
  const { t } = useTranslation();
  const c = inv.campaign;
  const order = directOrderOf(inv);
  const live = inv.proposal;
  /* A campaign that has ended keeps its card (the record of what was
     offered) but takes no more answers — the badge says why the forms are
     gone. The two endings are told apart rather than merged: being called off
     and running to the end are different news, and a creator reading "annulée"
     on a brief they delivered would be told something untrue. */
  const cancelled = c.status === "cancelled";
  const completed = c.status === "completed";
  const closed = CLOSED_CAMPAIGN_STATUSES.has(c.status);

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          {/* business_company_name is null until the brand fills its profile;
              a generic label beats an empty line above the title. */}
          <div className="muted" style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase" }}>
            {inv.business_company_name || t("invitation.brandFallback")}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <strong style={{ fontFamily: "var(--font-display)", fontSize: 18 }}>{c.title}</strong>
            {order && (
              <span style={{ fontSize: 12, fontWeight: 700, color: "#fff", background: "var(--indigo)", padding: "3px 10px", borderRadius: 999 }}>
                {t("invitation.orderBadge")}
              </span>
            )}
            {cancelled && (
              <span style={{ fontSize: 12, fontWeight: 700, color: "#9b2c2c", background: "#fdecec", padding: "3px 10px", borderRadius: 999 }}>
                {t("invitation.campaignCancelled")}
              </span>
            )}
            {/* Quiet rather than red: nothing went wrong here, the brief is
                simply over. */}
            {completed && (
              <span style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}>
                {t("invitation.campaignCompleted")}
              </span>
            )}
          </div>
        </div>
        {/* Translated rather than the raw enum: "withdrawn" on a French
            screen is the kind of leak the invitation list should not have. The
            same keys the filter chips use. */}
        <span className="muted" style={{ fontSize: 13 }}>{t(`lf.inv_${inv.status}`, inv.status)}</span>
      </div>

      {/* A brief is priced against a budget and a deadline. An order has
          neither to argue about: the price is already named and the timeline
          is on the offer below, so the line would only repeat itself. */}
      {!order && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 24px", marginTop: 10, fontSize: 14 }}>
          <span>
            <span className="muted">{t("campaign.budget")} : </span>
            {c.budget_amount ? `${c.budget_amount} ${c.budget_currency ?? ""}`.trim() : t("campaign.noBudget")}
          </span>
          <span>
            <span className="muted">{t("campaign.deadline")} : </span>
            {c.deadline || t("invitation.noDeadline")}
          </span>
        </div>
      )}

      {/* Same one-line-per-deliverable shape as the campaign recap, so the
          creator is pricing exactly the list the brand wrote — or, on an
          order, making exactly what was bought. */}
      <div style={{ marginTop: 16 }}>
        <span className="label">{t("campaign.deliverables")}</span>
        {c.deliverables.length === 0 ? (
          <p className="muted" style={{ fontSize: 14, margin: 0 }}>{t("campaign.noDeliverables")}</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14 }}>
            {c.deliverables.map((d, i) => (
              <li key={i}>{d.quantity} × {t(`deliverable.${d.type}`, d.type)} · {PLATFORM_LABELS[d.platform] ?? d.platform}</li>
            ))}
          </ul>
        )}
      </div>

      {/* WHAT THE BRAND MAY DO WITH THE CONTENT, under the deliverables and
          ABOVE the negotiation panel, which is where both of this card's
          decisions are made.

          THIS IS THE PLACEMENT THE FEATURE TURNS ON, and it covers BOTH kinds
          of row with one panel because both are answered here. On a brief the
          creator is about to type a rate into ProposalForm; on a direct order
          the Accepter button is a few centimetres below, and pressing it
          GENERATES THE CONTRACT whose article 10 carries whatever the brand
          stated. Either way the licence is part of what is being priced or
          signed, so it cannot sit below the control that does it.

          It stays on a closed or cancelled card too, where every form is gone:
          the card is then the record of what was offered, and what the brand
          would have been allowed to do with the content is part of that record.

          AND THE ROW IT READS IS THE OFFER'S FIRST, THE BRIEF'S SECOND, which
          is the backend's own precedence and not a choice this card makes. A
          brief's licence is written on the campaign; a DIRECT ORDER'S is
          written on the brand's proposal row, because there the proposal IS
          the offer and the campaign behind it is a wrapper nobody reads terms
          from. Reading `c` alone, which is what this card used to do, showed
          every direct order as "not stated" while the licence sat on the very
          proposal the Accepter button is addressed to.

          It is still not a term either side COUNTERS: a proposal version is a
          rate, a currency and a timeline, submit_proposal carries the brand's
          block forward onto a counter rather than taking a new one, and
          ProposalIn has no licence field at all. The block lives on a
          proposal because that is where the BRAND wrote it, not because the
          creator can answer it. licenceRowFor in lib/licence.ts is the one
          copy of the rule, and contracts.service._licence_snapshot applies
          the same order when the contract is finally written. */}
      <LicenceTerms row={licenceRowFor(live, c)} voice="creator" />

      {live ? (
        /* A live version means the negotiation has started, whoever opened it.
           The blank form below is for the other case only: a brief nobody has
           priced yet. Showing it while an offer is on the table is what used
           to hide the brand's counter behind an empty rate box. */
        <Negotiation
          campaignId={inv.campaign_id}
          live={live}
          /* ?? [] rather than a bare read: an older backend sends the row
             without a history at all, and the panel falls back to the live
             version rather than to nothing. */
          history={inv.proposal_history ?? []}
          isOrder={order !== null}
          readOnly={closed}
          onDone={onDone}
        />
      ) : closed ? null : (
        /* The rule above the line is the brand's; everything below it is the
           creator's answer, so the two are separated visually. */
        <div style={{ borderTop: "1px solid var(--line)", marginTop: 20, paddingTop: 16 }}>
          <span className="label" style={{ marginBottom: 10 }}>{t("invitation.yourProposal")}</span>
          <ProposalForm campaignId={inv.campaign_id} onDone={onDone} />
        </div>
      )}
    </div>
  );
}

export default function MyInvitations() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [invitations, setInvitations] = useState<InvitationWithCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  /* "" is all. Narrows on the invitation status the creator sees on each
     card. Filtered in memory. */
  const [statusFilter, setStatusFilter] = useState("");

  function load() {
    api<InvitationWithCampaign[]>("/campaigns/invitations/mine", { token })
      .then(setInvitations)
      .catch((e) => setError(errorText(e, t)))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token, t]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  /* Chips from the statuses actually present, labelled with the lf.inv_* keys
     the card now uses too. */
  const statusOptions: FilterOption[] = Array.from(new Set(invitations.map((i) => i.status))).map((s) => ({
    value: s,
    label: t(`lf.inv_${s}`, s)
  }));
  const shown = statusFilter ? invitations.filter((i) => i.status === statusFilter) : invitations;

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 760 }}>
        <h1>{t("invitation.title")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("invitation.sub")}</p>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {!loading && invitations.length > 0 && (
          <ListFilter options={statusOptions} value={statusFilter} onChange={setStatusFilter} />
        )}

        <div style={{ marginTop: 18 }}>
          {loading ? (
            <p className="muted">{t("discover.loading")}</p>
          ) : invitations.length === 0 ? (
            <div className="card"><p className="muted" style={{ margin: 0 }}>{t("invitation.empty")}</p></div>
          ) : shown.length === 0 ? (
            <div className="card"><p className="muted" style={{ margin: 0 }}>{t("filt.none")}</p></div>
          ) : (
            <div style={{ display: "grid", gap: 16 }}>
              {shown.map((inv) => (
                <InvitationCard key={inv.id} inv={inv} onDone={load} />
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
