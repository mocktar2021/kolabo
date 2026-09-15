import { useCallback, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorChip } from "../components/CreatorChip";
import { DeliverableRows } from "../components/DeliverableRows";
import { TargetingFields, targetingBody, targetingOf, type Targeting } from "../components/TargetingFields";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { CURRENCIES, MAX_DESCRIPTION_LENGTH } from "../lib/campaignOptions";
import type { CampaignDetail, Contract, Deliverable, Favorite, Proposal } from "../lib/types";

/* Mirrors MAX_NOTE_LENGTH in backend/app/modules/campaigns/schemas.py. */
const NOTE_MAX_LENGTH = 2000;

/* The campaign statuses that are over. Campaign.status is exactly draft,
   published, cancelled and completed; cancelled was called off and completed
   ran to the end, and editing.py answers 400 to a PATCH on either. The same
   pair MyInvitations.tsx closes a creator's forms on, held the same way, so
   the two sides of a finished brief agree on what ended means. */
const CLOSED_CAMPAIGN_STATUSES = new Set(["cancelled", "completed"]);

/* One favourited creator, offered as a person rather than as an id. "Créateur
   05317bc0" is not somebody a brand can decide to invite: the choice is made
   on a face, a name and the size of the audience behind them — which is what
   CreatorChip renders, identically here, in the invitations list below and on
   every proposal. */
function FavoriteRow({ fav, disabled, onInvite }: { fav: Favorite; disabled: boolean; onInvite: () => void }) {
  const { t } = useTranslation();
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
      <CreatorChip creator={fav} />
      <button className="btn btn-ghost" disabled={disabled} onClick={onInvite}>{t("campaign.invite")}</button>
    </div>
  );
}

/* One negotiation: every version exchanged with a single creator, oldest
   first, with the live offer last. */
type ProposalChain = { versions: Proposal[]; latest: Proposal };

/* The API hands back one flat list of versions for the whole campaign, so the
   chains are reassembled here. A chain is the set of rows sharing an
   influencer_user_id — business replies included, because a reply is another
   version of that creator's offer and not a message beside it. Insertion order
   is kept so the negotiations stay in the order the API sent them, and each
   chain is sorted by version rather than by arrival: version is what the
   backend numbers the chain by, and it is what "latest" has to mean. */
function buildChains(proposals: Proposal[]): ProposalChain[] {
  const byCreator = new Map<string, Proposal[]>();
  for (const p of proposals) {
    const existing = byCreator.get(p.influencer_user_id);
    if (existing) existing.push(p);
    else byCreator.set(p.influencer_user_id, [p]);
  }
  return Array.from(byCreator.values()).map((rows) => {
    const versions = [...rows].sort((a, b) => a.version - b.version);
    return { versions, latest: versions[versions.length - 1] };
  });
}

/* Correcting a brief in place, within what the people looking at it allow.

   THE RULE, and it is the backend's (backend/app/modules/campaigns/editing.py
   holds the authority; this form only mirrors it so the buyer meets it as a
   greyed-out field rather than as a 400). Title and description are
   description, not terms: rewrite them and a bid already on the table still
   means what it meant, so they never lock. Budget, currency, deliverables and
   deadline are what a creator PRICES AGAINST, and they lock the moment a
   proposal exists on a published campaign — somebody who bid 40k to make
   three posts against a 500k budget did not bid to make six against 200k, and
   silently rewriting that turns a submitted bid into a bid for different work
   which the contract would then be written from.

   TARGETING AND is_open ARE ON THE UNLOCKED SIDE, and deliberately: they are
   not terms. Nobody prices a brief against who else the brand was hoping to
   hear from, so widening the board — or closing it to new applications —
   takes nothing away from the offers already made. editing.py keeps them out
   of LOCKED_FIELDS for exactly that reason, so they stay editable here even
   once creators have bid.

   A draft locks nothing, and neither does a published campaign nobody has bid
   on: no creator has spent an evening pricing it, so fixing a budget with a
   missing zero costs nobody anything. The lock protects work already done,
   not the publish button.

   Locked fields are rendered read-only rather than dropped from the form. A
   budget that disappears reads as a bug; a budget shown greyed out with the
   reason under it reads as a rule. */
function CampaignEditor({ campaign, locked, onSaved, onClose }: {
  campaign: CampaignDetail;
  locked: boolean;
  onSaved: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [title, setTitle] = useState(campaign.title);
  const [description, setDescription] = useState(campaign.description ?? "");
  const [budget, setBudget] = useState(campaign.budget_amount ? String(campaign.budget_amount) : "");
  const [currency, setCurrency] = useState(campaign.budget_currency ?? CURRENCIES[0]);
  const [deadline, setDeadline] = useState(campaign.deadline ?? "");
  const [deliverables, setDeliverables] = useState<Deliverable[]>(campaign.deliverables);
  const [targeting, setTargeting] = useState<Targeting>(targetingOf(campaign));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    /* Only what actually changed goes in the body. PATCH is exclude_unset
       server-side, so a field the client does not send is left alone — and
       posting the whole form back would hand the lock check a budget to
       compare when the buyer only fixed a typo in the title. */
    const patch: Record<string, unknown> = {};
    if (title !== campaign.title) patch.title = title;
    if (description !== (campaign.description ?? "")) {
      // Explicit null clears the column, which is how a form empties a value.
      patch.description = description.trim() || null;
    }
    if (!locked) {
      const amount = budget ? Number(budget) : null;
      if (amount !== campaign.budget_amount) patch.budget_amount = amount;
      // A currency without an amount is not a budget. The two travel together
      // or both go null, exactly as the create form posts them.
      const cur = amount === null ? null : currency;
      if (cur !== campaign.budget_currency) patch.budget_currency = cur;
      const due = deadline || null;
      if (due !== campaign.deadline) patch.deadline = due;
      if (JSON.stringify(deliverables) !== JSON.stringify(campaign.deliverables)) {
        patch.deliverables = deliverables;
      }
    }
    /* OUTSIDE the lock, on purpose — see the rule above the component. An
       explicit [] on a targeting list is how a brand clears that dimension,
       and the server coerces a null to [] for the same reason, so an emptied
       picker is sent rather than silently skipped. */
    const target = targetingBody(targeting);
    if (target.is_open !== campaign.is_open) patch.is_open = target.is_open;
    if (JSON.stringify(target.target_categories) !== JSON.stringify(campaign.target_categories)) {
      patch.target_categories = target.target_categories;
    }
    if (JSON.stringify(target.target_countries) !== JSON.stringify(campaign.target_countries)) {
      patch.target_countries = target.target_countries;
    }
    if (target.target_min_followers !== campaign.target_min_followers) {
      patch.target_min_followers = target.target_min_followers;
    }
    if (target.target_max_followers !== campaign.target_max_followers) {
      patch.target_max_followers = target.target_max_followers;
    }
    if (Object.keys(patch).length === 0) {
      // Nothing to say. Closing beats posting an empty PATCH just to hear the
      // campaign read back unchanged.
      onClose();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}`, { method: "PATCH", token, body: patch });
      onSaved();
    } catch (e) {
      /* Whatever the server said, through errorText. editing.py answers 400
         NAMING the field that is locked and telling the buyer what to do
         instead (cancel and publish the new terms as a new brief), and that
         refusal carries no code yet — so its own English sentence is what
         shows, and a translated one takes over the day editing.py sends a
         code. Restating any of that here would be a second copy of a rule
         that lives there, and the copy is the one that drifts. */
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("campaign.editTitle")}</h3>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="field">
        <label className="label" htmlFor="e-title">{t("campaign.name")}</label>
        <input id="e-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>

      <div className="field">
        <label className="label" htmlFor="e-description">{t("campaign.description")}</label>
        <textarea id="e-description" className="input" rows={4} maxLength={MAX_DESCRIPTION_LENGTH}
          style={{ resize: "vertical" }} value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("campaign.descriptionPlaceholder")} />
      </div>

      {/* The locked half of the form. Same controls, disabled, with one muted
          line saying why — see the rule above the component. */}
      {locked && <p className="muted" style={{ fontSize: 13, margin: "0 0 10px" }}>{t("campaign.editLocked")}</p>}

      <div className="field" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
        <div>
          <label className="label" htmlFor="e-budget">{t("campaign.budget")}</label>
          <input id="e-budget" className="input" inputMode="numeric" value={budget} disabled={locked} readOnly={locked}
            onChange={(e) => setBudget(e.target.value.replace(/\D/g, ""))} placeholder="500000" />
        </div>
        <div>
          <label className="label" htmlFor="e-currency">{t("campaign.currency")}</label>
          <select id="e-currency" className="select" value={currency} disabled={locked}
            onChange={(e) => setCurrency(e.target.value)}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div className="field">
        <label className="label" htmlFor="e-deadline">{t("campaign.deadline")}</label>
        <input id="e-deadline" className="input" type="date" value={deadline} disabled={locked} readOnly={locked}
          onChange={(e) => setDeadline(e.target.value)} />
      </div>

      <div className="field">
        <span className="label">{t("campaign.deliverables")}</span>
        <DeliverableRows value={deliverables} onChange={setDeliverables} disabled={locked} />
      </div>

      {/* Never disabled, whatever `locked` says: targeting is not a term. */}
      <TargetingFields idPrefix="e" value={targeting} onChange={setTargeting} />

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className="btn btn-primary" disabled={busy || !title.trim()} onClick={save}>{t("campaign.saveEdit")}</button>
        <button className="btn btn-ghost" disabled={busy} onClick={onClose}>{t("campaign.cancelEdit")}</button>
      </div>
    </div>
  );
}

/* The business answering an offer. The note is required — a reply always says
   something — while the two term fields are optional and only sent when
   filled: the endpoint repeats the previous terms for anything omitted, so an
   empty box means "same terms", which is why the current ones sit in the
   placeholders. */
function ReplyForm({ campaignId, latest, onSent }: { campaignId: string; latest: Proposal; onSent: () => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [note, setNote] = useState("");
  const [rate, setRate] = useState("");
  const [days, setDays] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const trimmed = note.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaignId}/proposals/${latest.id}/reply`, {
        method: "POST",
        token,
        body: {
          note: trimmed,
          ...(rate ? { rate_amount: Number(rate) } : {}),
          ...(days ? { timeline_days: Number(days) } : {})
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
      <label className="label">{t("campaign.replyNote")}</label>
      <textarea
        className="input"
        rows={3}
        maxLength={NOTE_MAX_LENGTH}
        style={{ resize: "vertical" }}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder={t("campaign.replyNotePlaceholder")}
      />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10 }}>
        <div>
          <label className="label">{t("campaign.replyRate")}</label>
          <input
            className="input"
            inputMode="numeric"
            value={rate}
            onChange={(e) => setRate(e.target.value.replace(/\D/g, ""))}
            placeholder={String(latest.rate_amount)}
          />
        </div>
        <div>
          <label className="label">{t("campaign.replyDays")}</label>
          <input
            className="input"
            inputMode="numeric"
            value={days}
            onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))}
            placeholder={String(latest.timeline_days)}
          />
        </div>
      </div>
      <p className="hint" style={{ marginBottom: 10 }}>{t("campaign.replyHint")}</p>
      <button className="btn btn-primary" disabled={busy || !note.trim()} onClick={submit}>{t("campaign.replySend")}</button>
    </div>
  );
}

/* A negotiation read as a thread: every round in order, the live offer at the
   bottom carrying the emphasis and the buttons. Only the latest version can be
   accepted — everything above it has already been superseded by whoever wrote
   the row underneath, and signing a withdrawn offer would put terms in a
   contract that neither side is still standing behind.

   THREE ANSWERS, AND THEIR WEIGHTS ARE THE PRODUCT'S OPINION. Accept is
   primary because it is what a brief is for. Reply is next, because a number
   that is wrong is usually a number to argue about and every argument that
   leaves this page leaves the platform. Reject is last and quietest: it is the
   only one of the three that cannot be undone — the backend writes one of the
   three terminal statuses submit_proposal refuses to reopen, so that creator
   cannot come back with another version on this brief — so it is offered
   plainly, sized down, and behind a confirmation that says so. */
function ProposalThread({
  campaignId, chain, disabled, rejectable, onAccept, onViewContract, onReplied, onRejected
}: {
  campaignId: string;
  chain: ProposalChain;
  disabled: boolean;
  /* Off campaign.is_direct, mirroring the server. A direct order is closed by
     the creator declining it — which also cancels the order and tells the
     buyer they were not charged — so rejecting a version of one would leave it
     half-closed, and campaigns/rejections.py refuses it. The control is
     removed rather than left to be refused, the same way the invitation
     withdraw button is. */
  rejectable: boolean;
  onAccept: (proposalId: string) => void;
  onViewContract: (proposalId: string) => void;
  onReplied: () => void;
  onRejected: () => void;
}) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [replyOpen, setReplyOpen] = useState(false);
  /* Inline confirmation, never window.confirm — the same reason the campaign
     actions further down the page use one: a native dialog cannot be
     translated, cannot say what rejecting actually closes, and reads as a
     browser event rather than as part of the page. Per thread rather than
     shared, so a buyer with four bids open is never unsure which one they are
     about to end. */
  const [confirmingReject, setConfirmingReject] = useState(false);
  const [rejectBusy, setRejectBusy] = useState(false);
  const [rejectError, setRejectError] = useState<string | null>(null);
  const latest = chain.latest;
  // The brand wrote the live version, so the creator is the one being waited
  // on. Derived from author_role rather than stored, for the reason spelled
  // out in MyInvitations.tsx: a stored flag is a second copy of this fact and
  // the copy is the one that goes stale.
  const awaitingCreator = latest.author_role === "business";

  /* Turning the live offer down. Addressed to the latest version's id, which
     is the only one the server will act on — it rejects the live version of
     that creator's chain and nothing above it. */
  async function reject() {
    setRejectBusy(true);
    setRejectError(null);
    try {
      await api(`/campaigns/${campaignId}/proposals/${latest.id}/reject`, { method: "POST", token });
      setConfirmingReject(false);
      onRejected();
    } catch (e) {
      /* Off the CODE the refusal carries, through errorText: `proposal_closed`
         if the chain moved on in another tab, `proposal_has_contract` if it
         already produced one, `campaign_not_open` on a brief that ended while
         this page was open. Each of those is a different thing to do next, and
         the 400 they share names none of them. */
      setRejectError(errorText(e, t));
    } finally {
      setRejectBusy(false);
    }
  }

  return (
    <div style={{ borderTop: "1px solid var(--line)", padding: "14px 0" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <CreatorChip creator={latest} />
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {/* The mirror of the badge the creator reads on their invitations
              page, off the same field. Emphasis goes on the side that is
              waiting for this reader: "the creator replied" is the brand's
              turn to act, "waiting on the creator" is not. */}
          {latest.status === "submitted" && (
            <span
              style={awaitingCreator
                ? { fontSize: 12, fontWeight: 600, color: "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }
                : { fontSize: 12, fontWeight: 700, color: "#fff", background: "var(--teal-600)", padding: "3px 10px", borderRadius: 999 }}
            >
              {awaitingCreator ? t("campaign.awaitingCreator") : t("campaign.creatorReplied")}
            </span>
          )}
          <span className="muted" style={{ fontSize: 13 }}>{latest.status}</span>
        </div>
      </div>

      <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
        {chain.versions.map((v) => {
          const isLatest = v.id === latest.id;
          return (
            <div
              key={v.id}
              style={{
                borderLeft: `3px solid ${isLatest ? "var(--indigo)" : "var(--line)"}`,
                background: isLatest ? "var(--surface-2)" : "transparent",
                borderRadius: "0 var(--radius-sm) var(--radius-sm) 0",
                padding: "8px 12px"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, fontSize: 12.5 }}>
                <span style={{ fontWeight: 700 }}>
                  {v.author_role === "business" ? t("campaign.authorBrand") : t("campaign.authorCreator")}
                </span>
                <span className="muted">
                  {isLatest && <span style={{ color: "var(--indigo)", fontWeight: 600, marginRight: 8 }}>{t("campaign.currentOffer")}</span>}
                  v{v.version}
                </span>
              </div>
              <div style={{ fontSize: 14.5, fontWeight: isLatest ? 700 : 500 }}>
                {v.rate_amount} {v.rate_currency} · {v.timeline_days} {t("campaign.daysShort")}
              </div>
              {v.note && (
                <p className="muted" style={{ fontSize: 13.5, margin: "4px 0 0", whiteSpace: "pre-wrap" }}>{v.note}</p>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10, alignItems: "center" }}>
        {latest.status === "submitted" && (
          <>
            <button className="btn btn-primary" disabled={disabled} onClick={() => onAccept(latest.id)}>{t("campaign.accept")}</button>
            <button className="btn btn-ghost" disabled={disabled} onClick={() => setReplyOpen((o) => !o)}>{t("campaign.reply")}</button>
            {/* Visually secondary to both: smaller and muted, sized like the
                invitation withdraw button rather than like the two decisions
                beside it. */}
            {rejectable && !confirmingReject && (
              <button type="button" className="btn btn-ghost"
                style={{ padding: "5px 10px", fontSize: 13, color: "var(--muted)" }}
                disabled={disabled || rejectBusy}
                onClick={() => { setConfirmingReject(true); setRejectError(null); }}>
                {t("campaign.reject")}
              </button>
            )}
          </>
        )}
        {latest.status === "accepted" && (
          <button className="btn btn-ghost" disabled={disabled} onClick={() => onViewContract(latest.id)}>{t("campaign.viewContract")}</button>
        )}
      </div>

      {rejectError && <div className="alert alert-error" style={{ marginTop: 10 }}>{rejectError}</div>}

      {confirmingReject && latest.status === "submitted" && (
        <div style={{ marginTop: 10, borderLeft: "3px solid var(--line)", paddingLeft: 12 }}>
          <p className="muted" style={{ fontSize: 13.5, margin: "0 0 10px" }}>{t("campaign.rejectConfirm")}</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-ghost" disabled={disabled || rejectBusy} onClick={reject}>
              {t("campaign.rejectYes")}
            </button>
            <button type="button" className="btn btn-ghost" disabled={rejectBusy}
              onClick={() => { setConfirmingReject(false); setRejectError(null); }}>
              {t("campaign.rejectNo")}
            </button>
          </div>
        </div>
      )}

      {replyOpen && latest.status === "submitted" && (
        <ReplyForm
          campaignId={campaignId}
          latest={latest}
          onSent={() => { setReplyOpen(false); onReplied(); }}
        />
      )}
    </div>
  );
}

export default function CampaignDetailPage() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  /* Inline confirmation, never window.confirm: a native dialog cannot be
     translated, cannot say what cancelling actually does to the invited
     creators, and reads as a browser event rather than as part of the page
     the buyer is deciding on. */
  const [confirming, setConfirming] = useState<"cancel" | "delete" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  /* Which invitation is being taken back, by id. One at a time and inline on
     its own row, for the same reason the campaign confirmations are inline:
     the sentence that makes this decision easy — the creator is told, and
     withdrawn is not declined — does not fit in a browser dialog, and a
     shared confirmation would leave the buyer unsure which row they are
     about to act on. */
  const [withdrawingInvitation, setWithdrawingInvitation] = useState<string | null>(null);
  const [invitationError, setInvitationError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const data = await api<CampaignDetail>(`/campaigns/${id}`, { token });
      setCampaign(data);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setLoading(false);
    }
  }, [id, token, t]);

  useEffect(() => {
    load();
    api<Favorite[]>("/discovery/favorites", { token })
      .then(setFavorites)
      .catch(() => undefined);
  }, [load, token]);

  async function publish() {
    if (!campaign) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}/publish`, { method: "POST", token });
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function invite(influencerId: string) {
    if (!campaign) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}/invitations`, { method: "POST", token, body: { influencer_id: influencerId } });
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  /* Taking an invitation back while it is still only an invitation.

     The row is KEPT, with a 'withdrawn' status rather than deleted, and
     withdrawn is not declined: nobody said no here, and a creator's record
     should not carry a refusal they never made. The creator is notified —
     somebody invited on Monday who finds the row quietly gone on Friday has
     no way to tell being dropped from something being broken, and the ones
     who ask are the polite minority. */
  async function withdrawInvitation(invitationId: string) {
    if (!campaign) return;
    setBusy(true);
    setInvitationError(null);
    try {
      await api(`/campaigns/${campaign.id}/invitations/${invitationId}`, { method: "DELETE", token });
      setWithdrawingInvitation(null);
      await load();
    } catch (e) {
      /* Off the CODE the refusal carries rather than its status, which is
         finer than the 400 the two cases share: withdrawals.py sends
         `invitation_not_open` when the invitation has already moved on, and
         `invitation_priced` when the creator has priced the brief. The
         second is the one worth naming — there is an offer on the table to
         answer, which is somewhere to go rather than a dead end. */
      setInvitationError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  /* Calling the brief off. Nothing is removed: the status changes and every
     creator who was invited is told, because somebody holding a brief they
     are pricing deserves to hear it is dead rather than work it out from
     silence. */
  async function cancelCampaign() {
    if (!campaign) return;
    setBusy(true);
    setActionError(null);
    try {
      await api(`/campaigns/${campaign.id}/cancel`, { method: "POST", token });
      setConfirming(null);
      await load();
    } catch (e) {
      /* Mapped by the CODE the refusal carries. editing.py now sends
         `campaign_has_contract` on cancel, which says what the 409 could only
         imply: a contract exists on this campaign, and unwinding a signed
         agreement is the dispute and refund path. The status is no longer
         read here — a code names the rule, where a number names a class of
         rules and leaves the page guessing which one it met. */
      setActionError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  /* Erasing a draft nobody has seen. The row is gone afterwards, so there is
     nothing left to render — the page leaves for the list rather than sitting
     on a campaign that no longer exists. */
  async function deleteCampaign() {
    if (!campaign) return;
    setBusy(true);
    setActionError(null);
    try {
      await api(`/campaigns/${campaign.id}`, { method: "DELETE", token });
      navigate("/campaigns");
    } catch (e) {
      /* Same rule as cancel, off the code rather than the status:
         `campaign_has_activity` means the campaign has a proposal, an
         invitation or a contract on it, and the buyer is told to cancel
         instead, because deleting would take the other side's half of the
         record with it. */
      setActionError(errorText(e, t));
      setBusy(false);
    }
  }

  async function acceptProposal(proposalId: string) {
    setBusy(true);
    setError(null);
    try {
      const contract = await api<Contract>(`/contracts/from-proposal/${proposalId}`, { method: "POST", token });
      navigate(`/contracts/${contract.id}`);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function viewContract(proposalId: string) {
    setBusy(true);
    setError(null);
    try {
      const contract = await api<Contract>(`/contracts/by-proposal/${proposalId}`, { token });
      navigate(`/contracts/${contract.id}`);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const invitedIds = new Set((campaign?.invitations ?? []).map((i) => i.influencer_user_id));
  const invitableFavorites = favorites.filter((f) => !invitedIds.has(f.influencer_user_id));
  const chains = buildChains(campaign?.proposals ?? []);

  /* Which creators have priced this brief, in any version.

     Mirror of _proposal_exists in backend/app/modules/campaigns/withdrawals.py
     and it has to be ANY version, including superseded ones and statuses that
     have since moved on: the question is whether they did the work, and a
     chain that reached version four is four rounds of it. The invitation's
     own status cannot answer this — on a brief it stays 'invited' no matter
     how much negotiating happens underneath it, which is exactly why the
     button needs this set rather than the row it sits on. */
  const priced = new Set((campaign?.proposals ?? []).map((p) => p.influencer_user_id));

  /* The three questions the owner actions are made of, asked once.

     editable: a campaign that has ended is closed, whichever of the two
     endings it reached, and a direct order is a negotiation rather than a
     document — editing.py answers 400 to all of them, so none of them gets a
     form that could only fail.

     locked: the terms are frozen once a published campaign has been priced
     against. Exactly the backend's condition.

     deletable: a draft with nothing attached. The server also refuses when a
     contract exists, which cannot happen on a draft, and answers 409 either
     way — so this is the offer, not the authority. */
  const editable = !!campaign && !campaign.is_direct && !CLOSED_CAMPAIGN_STATUSES.has(campaign.status);
  const locked = !!campaign && campaign.status === "published" && campaign.proposals.length > 0;
  const deletable =
    !!campaign && campaign.status === "draft" &&
    campaign.proposals.length === 0 && campaign.invitations.length === 0;

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 760 }}>
        {error && <div className="alert alert-error">{error}</div>}
        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : !campaign ? (
          <p className="muted">{t("campaign.notFound")}</p>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h1 style={{ margin: 0 }}>{campaign.title}</h1>
              <span style={{ fontSize: 12, fontWeight: 600, color: campaign.status === "published" ? "var(--teal-600)" : "var(--muted)", background: "var(--surface-2)", padding: "3px 10px", borderRadius: 999 }}>
                {t(`campaign.status_${campaign.status}`, campaign.status)}
              </span>
            </div>
            <p className="muted" style={{ marginTop: 6 }}>
              {campaign.budget_amount ? `${campaign.budget_amount} ${campaign.budget_currency}` : t("campaign.noBudget")}
              {campaign.deadline ? ` - ${campaign.deadline}` : ""}
            </p>
            {campaign.description && (
              <p style={{ fontSize: 14.5, whiteSpace: "pre-wrap" }}>{campaign.description}</p>
            )}
            <ul style={{ paddingLeft: 18, fontSize: 14 }}>
              {campaign.deliverables.map((d, i) => (
                <li key={i}>{d.quantity} x {t(`deliverable.${d.type}`, d.type)} - {d.platform}</li>
              ))}
            </ul>
            {/* Whether strangers can answer this brief is the difference
                between three invited creators and thirty applications
                overnight, so the campaign says which it is rather than
                leaving the buyer to open the edit form to find out. */}
            {campaign.is_open && (
              <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("target.openHint")}</p>
            )}
            {/* A draft and nothing else. publish_campaign answers 400
                campaign_publish_not_draft to anything that is not one, and
                the negated pair this replaces read as "not published, not
                cancelled" — which a completed brief satisfies, so it was
                offered a Publish button whose only outcome was that refusal.
                The mobile screen has always tested for draft; this is web
                agreeing with it. */}
            {campaign.status === "draft" && (
              <button className="btn btn-teal" disabled={busy} onClick={publish}>{t("campaign.publish")}</button>
            )}

            {/* Owner-only by construction: GET /campaigns/{id} is owner-only
                and answers 403 to anybody else, so a campaign that loaded at
                all belongs to whoever is reading this. */}
            <div className="card" style={{ marginTop: 16 }}>
              {saved && <div className="alert alert-success">{t("campaign.editSaved")}</div>}
              {actionError && <div className="alert alert-error">{actionError}</div>}

              {campaign.is_direct ? (
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("campaign.directNotEditable")}</p>
              ) : campaign.status === "cancelled" ? (
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("campaign.cancelled")}</p>
              ) : confirming === "cancel" ? (
                <>
                  <p style={{ margin: "0 0 10px", fontSize: 14 }}>{t("campaign.cancelConfirm")}</p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button className="btn btn-primary" disabled={busy} onClick={cancelCampaign}>{t("campaign.cancelYes")}</button>
                    <button className="btn btn-ghost" disabled={busy} onClick={() => { setConfirming(null); setActionError(null); }}>{t("campaign.cancelNo")}</button>
                  </div>
                </>
              ) : confirming === "delete" ? (
                <>
                  <p style={{ margin: "0 0 10px", fontSize: 14 }}>{t("campaign.deleteConfirm")}</p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button className="btn btn-primary" disabled={busy} onClick={deleteCampaign}>{t("campaign.deleteYes")}</button>
                    <button className="btn btn-ghost" disabled={busy} onClick={() => { setConfirming(null); setActionError(null); }}>{t("campaign.deleteNo")}</button>
                  </div>
                </>
              ) : (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  {/* Only where the editor can actually open. editable is what
                      decides whether the form renders below, so on a completed
                      campaign this button used to toggle a panel that never
                      appeared. Mobile gates the same button on the same
                      flag. */}
                  {editable && (
                    <button className="btn btn-ghost" disabled={busy}
                      onClick={() => { setEditOpen((o) => !o); setSaved(false); }}>
                      {t("campaign.edit")}
                    </button>
                  )}
                  <button className="btn btn-ghost" disabled={busy} onClick={() => { setConfirming("cancel"); setActionError(null); }}>
                    {t("campaign.cancelCampaign")}
                  </button>
                  {/* Offered only for a draft with nothing attached. Anywhere
                      else the button would exist purely to answer 409: a
                      campaign somebody has bid on is the other party's record
                      too, and cancel is the exit that keeps it. */}
                  {deletable && (
                    <button className="btn btn-ghost" disabled={busy} onClick={() => { setConfirming("delete"); setActionError(null); }}>
                      {t("campaign.delete")}
                    </button>
                  )}
                  {!deletable && <span className="muted" style={{ fontSize: 13 }}>{t("campaign.deleteHint")}</span>}
                </div>
              )}
            </div>

            {editOpen && editable && (
              <CampaignEditor
                campaign={campaign}
                locked={locked}
                onSaved={async () => { setEditOpen(false); setSaved(true); await load(); }}
                onClose={() => setEditOpen(false)}
              />
            )}

            {campaign.status === "published" && (
              <div className="card" style={{ marginTop: 20 }}>
                <h3 style={{ marginTop: 0 }}>{t("campaign.inviteFromFavorites")}</h3>
                {invitableFavorites.length === 0 ? (
                  <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("campaign.noFavorites")}</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    {invitableFavorites.map((f) => (
                      <FavoriteRow
                        key={f.influencer_user_id}
                        fav={f}
                        disabled={busy}
                        onInvite={() => invite(f.influencer_user_id)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="card" style={{ marginTop: 20 }}>
              <h3 style={{ marginTop: 0 }}>{t("campaign.invitations")} ({campaign.invitations.length})</h3>
              {invitationError && <div className="alert alert-error">{invitationError}</div>}
              {campaign.invitations.length === 0 ? (
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("campaign.noInvitations")}</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {campaign.invitations.map((inv) => {
                    /* THE ONE CONDITION, and it is the backend's: an
                       invitation may be retracted while it is still only an
                       invitation. Once the creator has PROPOSED they have
                       priced the brief — read it, worked out what the shoot
                       costs, decided what their audience is worth — and what
                       is on the table is an offer that deserves an answer.
                       withdraw_invitation answers 400 in that case, so the
                       button is removed rather than left to be refused.

                       This also removes it on every direct order for free,
                       which is correct rather than incidental: an order always
                       carries the buyer's own proposal, and an order is closed
                       by the creator declining it, not by the buyer deleting
                       the invitation out from under it. */
                    const retractable = inv.status === "invited" && !priced.has(inv.influencer_user_id);
                    const confirmingThis = withdrawingInvitation === inv.id;
                    return (
                      <div key={inv.id}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                          <CreatorChip creator={inv} />
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span className="muted" style={{ fontSize: 13 }}>{inv.status}</span>
                            {retractable && !confirmingThis && (
                              <button type="button" className="btn btn-ghost" style={{ padding: "5px 10px", fontSize: 13 }}
                                disabled={busy}
                                onClick={() => { setWithdrawingInvitation(inv.id); setInvitationError(null); }}>
                                {t("undo.invitationWithdraw")}
                              </button>
                            )}
                          </div>
                        </div>
                        {confirmingThis && (
                          <div style={{ marginTop: 8, borderLeft: "3px solid var(--line)", paddingLeft: 12 }}>
                            <p className="muted" style={{ fontSize: 13.5, margin: "0 0 10px" }}>{t("undo.invitationConfirm")}</p>
                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                              <button type="button" className="btn btn-ghost" disabled={busy}
                                onClick={() => withdrawInvitation(inv.id)}>
                                {t("undo.invitationYes")}
                              </button>
                              <button type="button" className="btn btn-ghost" disabled={busy}
                                onClick={() => { setWithdrawingInvitation(null); setInvitationError(null); }}>
                                {t("undo.invitationNo")}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="card" style={{ marginTop: 16 }}>
              <h3 style={{ marginTop: 0, marginBottom: 4 }}>{t("campaign.proposals")} ({chains.length})</h3>
              {/* Said out loud, because the alternative is one WhatsApp message
                  away: a rate argued over somewhere else gets agreed somewhere
                  else, and a deal agreed off-platform has no contract, no
                  escrow and no recourse for either side. The line names what
                  the brand loses by leaving, not what we lose. */}
              <p className="muted" style={{ margin: "0 0 6px", fontSize: 13 }}>{t("campaign.keepOnPlatform")}</p>
              {chains.length === 0 ? (
                <p className="muted" style={{ margin: "8px 0 0", fontSize: 14 }}>{t("campaign.noProposals")}</p>
              ) : (
                chains.map((chain) => (
                  <ProposalThread
                    key={chain.latest.influencer_user_id}
                    campaignId={campaign.id}
                    chain={chain}
                    disabled={busy}
                    rejectable={!campaign.is_direct}
                    onAccept={acceptProposal}
                    onViewContract={viewContract}
                    onReplied={load}
                    onRejected={load}
                  />
                ))
              )}
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
