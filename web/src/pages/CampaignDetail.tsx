import { useCallback, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { CreatorChip } from "../components/CreatorChip";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { CampaignDetail, Contract, Favorite, Proposal } from "../lib/types";

/* Mirrors MAX_NOTE_LENGTH in backend/app/modules/campaigns/schemas.py. */
const NOTE_MAX_LENGTH = 2000;

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
      setError(e instanceof Error ? e.message : "Error");
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
   contract that neither side is still standing behind. */
function ProposalThread({
  campaignId, chain, disabled, onAccept, onViewContract, onReplied
}: {
  campaignId: string;
  chain: ProposalChain;
  disabled: boolean;
  onAccept: (proposalId: string) => void;
  onViewContract: (proposalId: string) => void;
  onReplied: () => void;
}) {
  const { t } = useTranslation();
  const [replyOpen, setReplyOpen] = useState(false);
  const latest = chain.latest;
  // The brand wrote the live version, so the creator is the one being waited
  // on. Derived from author_role rather than stored, for the reason spelled
  // out in MyInvitations.tsx: a stored flag is a second copy of this fact and
  // the copy is the one that goes stale.
  const awaitingCreator = latest.author_role === "business";

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

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
        {latest.status === "submitted" && (
          <>
            <button className="btn btn-primary" disabled={disabled} onClick={() => onAccept(latest.id)}>{t("campaign.accept")}</button>
            <button className="btn btn-ghost" disabled={disabled} onClick={() => setReplyOpen((o) => !o)}>{t("campaign.reply")}</button>
          </>
        )}
        {latest.status === "accepted" && (
          <button className="btn btn-ghost" disabled={disabled} onClick={() => onViewContract(latest.id)}>{t("campaign.viewContract")}</button>
        )}
      </div>

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

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const data = await api<CampaignDetail>(`/campaigns/${id}`, { token });
      setCampaign(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [id, token]);

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
      setError(e instanceof Error ? e.message : "Error");
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
      setError(e instanceof Error ? e.message : "Error");
    } finally {
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
      setError(e instanceof Error ? e.message : "Error");
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
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const invitedIds = new Set((campaign?.invitations ?? []).map((i) => i.influencer_user_id));
  const invitableFavorites = favorites.filter((f) => !invitedIds.has(f.influencer_user_id));
  const chains = buildChains(campaign?.proposals ?? []);

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
            <ul style={{ paddingLeft: 18, fontSize: 14 }}>
              {campaign.deliverables.map((d, i) => (
                <li key={i}>{d.quantity} x {t(`deliverable.${d.type}`, d.type)} - {d.platform}</li>
              ))}
            </ul>
            {campaign.status !== "published" && (
              <button className="btn btn-teal" disabled={busy} onClick={publish}>{t("campaign.publish")}</button>
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
              {campaign.invitations.length === 0 ? (
                <p className="muted" style={{ margin: 0, fontSize: 14 }}>{t("campaign.noInvitations")}</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {campaign.invitations.map((inv) => (
                    <div key={inv.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                      <CreatorChip creator={inv} />
                      <span className="muted" style={{ fontSize: 13 }}>{inv.status}</span>
                    </div>
                  ))}
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
                    onAccept={acceptProposal}
                    onViewContract={viewContract}
                    onReplied={load}
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
