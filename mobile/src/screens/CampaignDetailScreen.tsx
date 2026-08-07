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
import { Banner, GhostButton, Hint, PrimaryButton, Screen, SectionTitle, Subtitle, Title } from "../components/ui";
import { colors, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* The owner's view of one campaign: the brief as published, who was invited,
   and every negotiation underneath it. Mirrors the web CampaignDetail's
   reading half against the same endpoints. Editing, cancelling and inviting
   from favourites stay web-side for now — the mobile owner reads, answers and
   accepts, which is the daily loop; correcting a brief is a desk task.

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
        <View style={{ marginBottom: space(2) }}>
          <GhostButton title={t("common.back")} onPress={() => navigation.goBack()} />
        </View>
        <Banner kind="error">{t("campaign.notFound")}</Banner>
      </Screen>
    );
  }

  const chains = campaign ? buildChains(campaign.proposals) : [];

  return (
    <Screen>
      <View style={{ marginBottom: space(2) }}>
        <GhostButton title={t("common.back")} onPress={() => navigation.goBack()} />
      </View>

      {error ? <Banner kind="error">{error}</Banner> : null}
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

          <SectionTitle>{t("campaign.invitationsTitle")}</SectionTitle>
          {campaign.invitations.length === 0 ? (
            <Hint>{t("campaign.noInvitations")}</Hint>
          ) : (
            <View style={{ gap: space(2) }}>
              {campaign.invitations.map((inv) => (
                <View key={inv.id} style={styles.invRow}>
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
              ))}
            </View>
          )}

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
    fontWeight: "600",
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
    marginTop: space(1),
  },
  chipPublished: { backgroundColor: "#e7f6f0", color: colors.teal600 },
  chipMuted: { backgroundColor: colors.surface2, color: colors.muted },
  desc: { fontSize: font.small, color: colors.ink, marginBottom: space(2) },
  deliv: { fontSize: font.small, color: colors.ink },
  invRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space(2),
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
  },
  invName: { fontSize: font.small, fontWeight: "600", color: colors.ink, flexShrink: 1 },
  invStatus: { fontSize: font.tiny, color: colors.muted },
});
