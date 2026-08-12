import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/dates";
import { PLATFORM_LABELS, deliverableLabel } from "../lib/platforms";
import { buildChains, type CampaignDetailData } from "../lib/campaignTypes";
import type { Contract } from "../lib/contractTypes";
import { ProposalThread } from "../components/campaigns/ProposalThread";
import { CampaignEditForm } from "../components/campaigns/CampaignEditForm";
import { Banner, GhostButton, Hint, PrimaryButton, Screen, SectionTitle, Subtitle, Title } from "../components/ui";
import { colors, family, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* One row of GET /discovery/favorites — the shared creator identity. */
type Favorite = {
  influencer_user_id: string;
  display_name: string | null;
  avatar_url: string | null;
  top_platform: string | null;
  top_follower_count: number | null;
  country_code: string | null;
};

/* The owner's view of one campaign: the brief as published, who was invited,
   and every negotiation underneath it — plus the owner's own verbs: edit
   (within what the lock allows), cancel, delete a virgin draft, invite from
   favourites, and take an unanswered invitation back.

   Accepting is the money moment: POST /contracts/from-proposal/{id} writes
   the contract from the live version's terms and this screen routes straight
   to it, because signing is the next thing the buyer has to do. */
export default function CampaignDetailScreen({ navigation, route }: AppScreenProps<"CampaignDetail">) {
  const { id } = route.params;
  const { t, i18n } = useTranslation();
  const { token } = useAuth();

  const [campaign, setCampaign] = useState<CampaignDetailData | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  /* Inline confirmations, never a system alert: the sentence that makes each
     decision easy has to be readable and translated. One slot for the two
     campaign-level acts; invitation withdrawal confirms on its own row so the
     buyer is never unsure which row they are about to act on. */
  const [confirming, setConfirming] = useState<"cancel" | "delete" | null>(null);
  const [withdrawingInvitation, setWithdrawingInvitation] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [invitingId, setInvitingId] = useState<string | null>(null);

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      setCampaign(await api<CampaignDetailData>(`/campaigns/${id}`, { token }));
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setNotFound(true);
      else setError(errorText(e, t));
    }
  }, [id, token, t]);

  useEffect(() => navigation.addListener("focus", () => void load()), [navigation, load]);
  useEffect(() => {
    void load();
  }, [load]);

  // Favourites feed the invite section; a failure just leaves it empty.
  useEffect(() => {
    if (!token) return;
    api<Favorite[]>("/discovery/favorites", { token })
      .then(setFavorites)
      .catch(() => setFavorites([]));
  }, [token]);

  async function invite(influencerId: string) {
    if (!campaign) return;
    setInvitingId(influencerId);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}/invitations`, {
        method: "POST",
        token,
        body: { influencer_id: influencerId },
      });
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setInvitingId(null);
    }
  }

  async function withdrawInvitation(invitationId: string) {
    if (!campaign) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}/invitations/${invitationId}`, {
        method: "DELETE",
        token,
      });
      setWithdrawingInvitation(null);
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function cancelCampaign() {
    if (!campaign) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}/cancel`, { method: "POST", token });
      setConfirming(null);
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function deleteCampaign() {
    if (!campaign) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}`, { method: "DELETE", token });
      // The row it names no longer exists; the list is the only place to go.
      navigation.navigate("Campaigns");
    } catch (e) {
      setError(errorText(e, t));
      setBusy(false);
    }
  }

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

  async function acceptProposal(proposalId: string) {
    setBusy(true);
    setError(null);
    try {
      const contract = await api<Contract>(`/contracts/from-proposal/${proposalId}`, {
        method: "POST",
        token,
      });
      navigation.navigate("ContractDetail", { id: contract.id });
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
      navigation.navigate("ContractDetail", { id: contract.id });
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  if (notFound) {
    return (
      <Screen>
        <Banner kind="error">{t("campaign.notFound")}</Banner>
      </Screen>
    );
  }

  const chains = campaign ? buildChains(campaign.proposals) : [];

  /* The three questions the owner actions are made of, asked once — the
     backend's conditions, mirrored so the buyer meets them as absent buttons
     rather than 400s (editing.py stays the authority either way). */
  const editable = !!campaign && !campaign.is_direct && campaign.status !== "cancelled";
  const locked = !!campaign && campaign.status === "published" && campaign.proposals.length > 0;
  const deletable =
    !!campaign &&
    campaign.status === "draft" &&
    campaign.proposals.length === 0 &&
    campaign.invitations.length === 0;
  /* Which creators have priced this brief, in ANY version, including
     superseded ones: the question is whether they did the work, and the
     invitation's own status cannot answer it — on a brief it stays "invited"
     no matter how much negotiating happens underneath. Mirror of
     _proposal_exists in campaigns/withdrawals.py. */
  const priced = new Set((campaign?.proposals ?? []).map((p) => p.influencer_user_id));
  const invitedIds = new Set((campaign?.invitations ?? []).map((i) => i.influencer_user_id));
  const invitableFavorites = favorites.filter((f) => !invitedIds.has(f.influencer_user_id));

  return (
    <Screen
      loading={campaign === null && !error}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}
      {campaign === null ? null : (
        <>
          <View style={styles.headRow}>
            <Title>{campaign.title}</Title>
            <Text
              style={[
                styles.chip,
                campaign.status === "published" ? styles.chipPublished : styles.chipMuted,
              ]}
            >
              {t(`campaign.status_${campaign.status}`, { defaultValue: campaign.status })}
            </Text>
          </View>
          <Subtitle>
            {campaign.budget_amount
              ? `${campaign.budget_amount.toLocaleString(i18n.language)} ${campaign.budget_currency}`
              : t("campaign.noBudget")}
            {campaign.deadline ? ` · ${formatDate(campaign.deadline, i18n.language)}` : ""}
          </Subtitle>

          {campaign.description ? <Text style={styles.desc}>{campaign.description}</Text> : null}

          {campaign.deliverables.length > 0 ? (
            <View style={{ gap: 2, marginBottom: space(2) }}>
              {campaign.deliverables.map((d, i) => (
                <Text key={i} style={styles.deliv}>
                  {d.quantity} × {deliverableLabel(d.type)} — {PLATFORM_LABELS[d.platform] ?? d.platform}
                </Text>
              ))}
            </View>
          ) : (
            <Hint>{t("campaign.noDeliverables")}</Hint>
          )}

          {campaign.is_open ? <Hint>{t("target.openHint")}</Hint> : null}

          {campaign.status === "draft" && !campaign.is_direct ? (
            <View style={{ marginTop: space(3) }}>
              <PrimaryButton
                title={busy ? t("common.working") : t("campaign.publish")}
                onPress={publish}
                loading={busy}
              />
            </View>
          ) : null}

          {campaign.status === "cancelled" ? (
            <View style={{ marginTop: space(2) }}>
              <Banner kind="info">{t("campaign.cancelled")}</Banner>
            </View>
          ) : null}
          {campaign.is_direct && campaign.status !== "cancelled" ? (
            <Hint>{t("campaign.directNotEditable")}</Hint>
          ) : null}
          {saved ? <Banner kind="success">{t("campaign.editSaved")}</Banner> : null}

          {/* The owner's verbs on the campaign itself. Confirmations are
              inline; each states what the act actually does before the
              button that does it. */}
          {editOpen && campaign ? (
            <CampaignEditForm
              campaign={campaign}
              locked={locked}
              onSaved={() => {
                setEditOpen(false);
                setSaved(true);
                void load();
              }}
              onClose={() => setEditOpen(false)}
            />
          ) : confirming === "cancel" ? (
            <View style={{ marginTop: space(3) }}>
              <Hint>{t("campaign.cancelConfirm")}</Hint>
              <View style={{ height: space(2) }} />
              <GhostButton title={t("campaign.cancelYes")} onPress={() => void cancelCampaign()} disabled={busy} />
              <View style={{ height: space(2) }} />
              <GhostButton title={t("campaign.cancelNo")} onPress={() => setConfirming(null)} disabled={busy} />
            </View>
          ) : confirming === "delete" ? (
            <View style={{ marginTop: space(3) }}>
              <Hint>{t("campaign.deleteConfirm")}</Hint>
              <View style={{ height: space(2) }} />
              <GhostButton title={t("campaign.deleteYes")} onPress={() => void deleteCampaign()} disabled={busy} />
              <View style={{ height: space(2) }} />
              <GhostButton title={t("campaign.deleteNo")} onPress={() => setConfirming(null)} disabled={busy} />
            </View>
          ) : (
            <View style={{ marginTop: space(3), gap: space(2) }}>
              {editable ? (
                <GhostButton
                  title={t("campaign.edit")}
                  onPress={() => {
                    setSaved(false);
                    setEditOpen(true);
                  }}
                  disabled={busy}
                />
              ) : null}
              {campaign.status !== "cancelled" ? (
                <GhostButton
                  title={t("campaign.cancelCampaign")}
                  onPress={() => setConfirming("cancel")}
                  disabled={busy}
                />
              ) : null}
              {deletable ? (
                <GhostButton
                  title={t("campaign.delete")}
                  onPress={() => setConfirming("delete")}
                  disabled={busy}
                />
              ) : null}
            </View>
          )}

          <SectionTitle>{t("campaign.invitationsTitle")}</SectionTitle>
          {campaign.invitations.length === 0 ? (
            <Hint>{t("campaign.noInvitations")}</Hint>
          ) : (
            <View style={{ gap: space(2) }}>
              {campaign.invitations.map((inv) => {
                /* Withdrawable only while unanswered AND unpriced: once the
                   creator has priced the brief there is an offer to answer,
                   not an invitation to retract — the backend refuses with a
                   400 saying so. */
                const withdrawable =
                  inv.status === "invited" && !priced.has(inv.influencer_user_id);
                return (
                  <View key={inv.id} style={styles.invRow}>
                    <View style={styles.invTop}>
                      <Text style={styles.invName} numberOfLines={1}>
                        {inv.display_name || t("campaign.unnamedCreator")}
                        {inv.top_follower_count
                          ? `  ·  ${inv.top_follower_count.toLocaleString(i18n.language)}`
                          : ""}
                      </Text>
                      <Text style={styles.invStatus}>
                        {t(`invitation.status_${inv.status}`, { defaultValue: inv.status })}
                      </Text>
                    </View>
                    {withdrawingInvitation === inv.id ? (
                      <View style={{ marginTop: space(2) }}>
                        <Hint>{t("campaign.withdrawInviteConfirm")}</Hint>
                        <View style={{ height: space(2) }} />
                        <GhostButton
                          title={t("campaign.withdrawInviteYes")}
                          onPress={() => void withdrawInvitation(inv.id)}
                          disabled={busy}
                        />
                        <View style={{ height: space(2) }} />
                        <GhostButton
                          title={t("campaign.withdrawInviteNo")}
                          onPress={() => setWithdrawingInvitation(null)}
                          disabled={busy}
                        />
                      </View>
                    ) : withdrawable ? (
                      <Text
                        style={styles.invWithdraw}
                        onPress={() => setWithdrawingInvitation(inv.id)}
                      >
                        {t("campaign.withdrawInvite")}
                      </Text>
                    ) : null}
                  </View>
                );
              })}
            </View>
          )}

          {/* Inviting somebody needs a published, non-direct campaign — the
              backend refuses anything else, so the section only appears when
              the invite can succeed. Candidates come from favourites, minus
              anyone already on the list above. */}
          {campaign.status === "published" && !campaign.is_direct ? (
            <>
              <SectionTitle>{t("campaign.inviteFromFavorites")}</SectionTitle>
              {invitableFavorites.length === 0 ? (
                <Hint>{t("campaign.noFavorites")}</Hint>
              ) : (
                <View style={{ gap: space(2) }}>
                  {invitableFavorites.map((f) => (
                    <View key={f.influencer_user_id} style={styles.invRow}>
                      <View style={styles.invTop}>
                        <Text style={styles.invName} numberOfLines={1}>
                          {f.display_name || t("campaign.unnamedCreator")}
                          {f.top_follower_count
                            ? `  ·  ${f.top_follower_count.toLocaleString(i18n.language)}`
                            : ""}
                        </Text>
                        <Text
                          style={styles.invite}
                          onPress={
                            invitingId ? undefined : () => void invite(f.influencer_user_id)
                          }
                        >
                          {invitingId === f.influencer_user_id
                            ? t("common.working")
                            : t("campaign.invite")}
                        </Text>
                      </View>
                    </View>
                  ))}
                </View>
              )}
            </>
          ) : null}

          <SectionTitle>{t("campaign.proposalsTitle")}</SectionTitle>
          {chains.length === 0 ? (
            <Hint>{t("campaign.noProposals")}</Hint>
          ) : (
            <View>
              {chains.map((chain) => (
                <ProposalThread
                  key={chain.latest.influencer_user_id}
                  campaignId={campaign.id}
                  chain={chain}
                  disabled={busy}
                  onAccept={(pid) => void acceptProposal(pid)}
                  onViewContract={(pid) => void viewContract(pid)}
                  onReplied={() => void load()}
                />
              ))}
            </View>
          )}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  headRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: space(2) },
  chip: {
    fontSize: font.tiny,
    fontFamily: family.bodySemi,
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
    marginTop: space(1),
  },
  chipPublished: { backgroundColor: "#e7f6f0", color: colors.teal600 },
  chipMuted: { backgroundColor: colors.surface2, color: colors.muted },
  desc: { fontFamily: family.body, fontSize: font.small, color: colors.ink, marginBottom: space(2) },
  deliv: { fontFamily: family.body, fontSize: font.small, color: colors.ink },
  invRow: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
  },
  invTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space(2),
  },
  invName: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, flexShrink: 1 },
  invStatus: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted },
  invWithdraw: { fontSize: font.tiny, color: colors.danger, fontFamily: family.bodySemi, marginTop: space(2) },
  invite: { fontSize: font.small, color: colors.teal600, fontFamily: family.bodyBold },
});
