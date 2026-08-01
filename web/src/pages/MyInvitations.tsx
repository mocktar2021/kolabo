import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CURRENCIES } from "../lib/campaignOptions";
import { PLATFORM_LABELS } from "../lib/platforms";
import type { Contract, InvitationWithCampaign, Proposal } from "../lib/types";

/* Mirrors MAX_NOTE_LENGTH in backend/app/modules/campaigns/schemas.py. Enforced
   here too so the limit is hit as a full textarea rather than as a 422 after
   the creator has finished typing. */
const NOTE_MAX_LENGTH = 2000;

/* The API serialises naive UTC datetimes ("2026-07-31T09:12:00", no suffix),
   which JavaScript reads as LOCAL time. Left alone that silently invents or
   destroys an hour of the window depending on where the creator is sitting,
   which on a 48 h clock is the difference between answering and lapsing. */
function parseUtc(iso: string): number {
  const time = iso.slice(10);
  const hasZone = time.endsWith("Z") || /[+-]\d\d:?\d\d$/.test(time);
  return Date.parse(hasZone ? iso : `${iso}Z`);
}

/* How long is left on an order, or null once it has lapsed. Computed at render
   rather than on a ticking timer: the server is the authority on expiry and
   answers "This order has expired." to a late click, which the card shows
   inline — so a stale minute on screen costs nothing but a second attempt.
   Never reports "0 min" while the offer is still live. */
function timeLeft(expiresAt: string): { unit: "hours" | "minutes"; n: number } | null {
  const ms = parseUtc(expiresAt) - Date.now();
  if (ms <= 0) return null;
  const minutes = Math.floor(ms / 60000);
  if (minutes < 60) return { unit: "minutes", n: Math.max(minutes, 1) };
  return { unit: "hours", n: Math.floor(minutes / 60) };
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
      setError(e instanceof Error ? e.message : "Error");
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

/* The terms of a direct order, and the two answers to it.

   Nothing here is a form. On a brief the creator names the price; on an order
   the brand already did, from the creator's own published package — so the
   numbers are printed, not typed, and the only decision left is yes or no.

   A direct order is a private transaction, not a public brief: it came to
   this creator alone and nobody else can see or bid on it. */
function OrderTerms({ inv, proposal, onDone }: { inv: InvitationWithCampaign; proposal: Proposal; onDone: () => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [confirmingDecline, setConfirmingDecline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const left = proposal.expires_at ? timeLeft(proposal.expires_at) : null;
  const expired = left === null;
  // Superseded, accepted or declined: already answered, so there is nothing
  // left to act on and the row is history.
  const open = proposal.status === "submitted";

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      /* Accepting is what creates the contract — the endpoint returns it, and
         signing is the next thing both sides have to do, so that is where the
         creator goes. Money still has not moved: escrow is funded by the buyer
         after both signatures. */
      const contract = await api<Contract>(`/campaigns/orders/${proposal.id}/accept`, { method: "POST", token });
      navigate(`/contracts/${contract.id}`);
    } catch (e) {
      // Covers the late click: "This order has expired." arrives as a 400 and
      // is shown as the server wrote it.
      setError(e instanceof Error ? e.message : "Error");
      setBusy(false);
    }
  }

  async function decline() {
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/orders/${proposal.id}/decline`, { method: "POST", token });
      // Reload rather than patch locally: the invitation status, the campaign
      // status and the proposal status all move together server-side.
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ borderTop: "1px solid var(--line)", marginTop: 20, paddingTop: 16 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 24px", fontSize: 14 }}>
        <span>
          <span className="muted">{t("invitation.orderPrice")} : </span>
          <strong>{proposal.rate_amount} {proposal.rate_currency}</strong>
        </span>
        <span>
          <span className="muted">{t("invitation.orderDelay")} : </span>
          {proposal.timeline_days} {t("campaign.daysShort")}
        </span>
      </div>

      {proposal.note && (
        <div style={{ marginTop: 12 }}>
          <span className="label">{t("invitation.orderNote")}</span>
          <p style={{ fontSize: 14, margin: 0, whiteSpace: "pre-wrap" }}>{proposal.note}</p>
        </div>
      )}

      {/* The clock, stated in the unit that is still useful: hours while there
          is a day left, minutes in the last stretch. */}
      <p className="muted" style={{ fontSize: 13, margin: "12px 0 0", fontWeight: expired ? 600 : 400 }}>
        {expired
          ? t("invitation.orderExpired")
          : left.unit === "hours"
            ? t("invitation.orderExpiresHours", { n: left.n })
            : t("invitation.orderExpiresMinutes", { n: left.n })}
      </p>

      {error && <div className="alert alert-error" style={{ marginTop: 12, marginBottom: 0 }}>{error}</div>}

      {open && (
        confirmingDecline ? (
          <div style={{ marginTop: 14 }}>
            {/* Inline, not a window.confirm: the sentence that makes this an
                easy decision — no money has moved, so a no costs the brand
                nothing but the wait — does not fit in a browser dialog. */}
            <p className="muted" style={{ fontSize: 13.5, margin: "0 0 10px" }}>{t("invitation.orderDeclineConfirm")}</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-ghost" disabled={busy} onClick={decline}>{t("invitation.orderDeclineYes")}</button>
              <button className="btn btn-ghost" disabled={busy} onClick={() => setConfirmingDecline(false)}>{t("invitation.orderDeclineNo")}</button>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
            <button className="btn btn-primary" disabled={busy || expired} onClick={accept}>{t("invitation.orderAccept")}</button>
            <button className="btn btn-ghost" disabled={busy || expired} onClick={() => setConfirmingDecline(true)}>{t("invitation.orderDecline")}</button>
          </div>
        )
      )}
    </div>
  );
}

/* One invitation, read top to bottom the way the decision is actually made:
   who is asking, what they want made, what they budgeted, by when — and only
   at the bottom, what the creator wants to be paid. Quoting a number before
   seeing the deliverables was guesswork.

   Two kinds of row share this card. A live proposal carrying expires_at means
   a brand bought a package outright and the terms are already set; anything
   else is a brief to price. Only direct orders run on a clock, which is what
   makes that field the test. */
function InvitationCard({ inv, onDone }: { inv: InvitationWithCampaign; onDone: () => void }) {
  const { t } = useTranslation();
  const c = inv.campaign;
  const order = inv.proposal && inv.proposal.expires_at ? inv.proposal : null;

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
          </div>
        </div>
        <span className="muted" style={{ fontSize: 13 }}>{inv.status}</span>
      </div>

      {/* A brief is priced against a budget and a deadline. An order has
          neither to argue about: the price is the package's and the timeline
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
              <li key={i}>{d.quantity} × {t(`deliverable.${d.type}`, d.type)} — {PLATFORM_LABELS[d.platform] ?? d.platform}</li>
            ))}
          </ul>
        )}
      </div>

      {order ? (
        <OrderTerms inv={inv} proposal={order} onDone={onDone} />
      ) : (
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

  function load() {
    api<InvitationWithCampaign[]>("/campaigns/invitations/mine", { token })
      .then(setInvitations)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 760 }}>
        <h1>{t("invitation.title")}</h1>
        <p className="muted" style={{ marginTop: -6 }}>{t("invitation.sub")}</p>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        <div style={{ marginTop: 18 }}>
          {loading ? (
            <p className="muted">{t("discover.loading")}</p>
          ) : invitations.length === 0 ? (
            <div className="card"><p className="muted" style={{ margin: 0 }}>{t("invitation.empty")}</p></div>
          ) : (
            <div style={{ display: "grid", gap: 16 }}>
              {invitations.map((inv) => (
                <InvitationCard key={inv.id} inv={inv} onDone={load} />
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
