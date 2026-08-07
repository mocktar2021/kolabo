import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/dates";
import type { Campaign } from "../lib/campaignTypes";
import { Banner, GhostButton, Hint, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const published = status === "published";
  return (
    <Text style={[styles.chip, published ? styles.chipPublished : styles.chipMuted]}>
      {t(`campaign.status_${status}`, { defaultValue: status })}
    </Text>
  );
}

export default function CampaignsListScreen({ navigation }: AppScreenProps<"Campaigns">) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [publishingId, setPublishingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setCampaigns(await api<Campaign[]>("/campaigns/mine", { token }));
      setError(null);
    } catch (e) {
      setError(errorText(e, t));
    }
  }, [token, t]);

  // Reload on focus so a campaign created on the New screen and navigated back
  // from is here, and a just-published draft shows its new status.
  useEffect(() => navigation.addListener("focus", () => void load()), [navigation, load]);
  useEffect(() => {
    void load();
  }, [load]);

  async function publish(id: string) {
    setPublishingId(id);
    setError(null);
    try {
      await api(`/campaigns/${id}/publish`, { method: "POST", token });
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setPublishingId(null);
    }
  }

  const loading = campaigns === null;
  const empty = !loading && campaigns.length === 0;

  return (
    <Screen>
      <View style={{ marginBottom: space(2) }}>
        <GhostButton title={t("common.back")} onPress={() => navigation.goBack()} />
      </View>
      <Title>{t("campaign.listTitle")}</Title>
      <Subtitle>{t("campaign.listSub")}</Subtitle>

      <View style={{ marginBottom: space(4) }}>
        <PrimaryButton title={t("campaign.new")} onPress={() => navigation.navigate("CampaignNew")} />
      </View>

      {error ? <Banner kind="error">{error}</Banner> : null}

      {loading ? null : empty ? (
        <>
          <Text style={styles.emptyText}>{t("campaign.listEmpty")}</Text>
          <Hint>{t("campaign.listEmptyHint")}</Hint>
        </>
      ) : (
        <View style={{ gap: space(2) }}>
          {campaigns.map((c) => (
            <View key={c.id} style={styles.row}>
              <View style={styles.rowTop}>
                <Text style={styles.rowTitle}>{c.title}</Text>
                <StatusChip status={c.status} />
              </View>
              <Text style={styles.rowMeta}>
                {c.budget_amount
                  ? `${c.budget_amount.toLocaleString(i18n.language)} ${c.budget_currency}`
                  : t("campaign.noBudget")}
                {c.deadline ? ` · ${formatDate(c.deadline, i18n.language)}` : ""}
              </Text>
              <View style={styles.rowTags}>
                {c.is_direct ? <Text style={styles.tag}>{t("campaign.tagOrder")}</Text> : null}
                {c.is_open ? <Text style={styles.tag}>{t("campaign.tagOpen")}</Text> : null}
                <Text style={styles.tag}>{t("campaign.deliverableCount", { n: c.deliverables.length })}</Text>
              </View>
              {c.status === "draft" && !c.is_direct ? (
                <View style={{ marginTop: space(3) }}>
                  <PrimaryButton
                    title={publishingId === c.id ? t("common.working") : t("campaign.publish")}
                    onPress={() => publish(c.id)}
                    loading={publishingId === c.id}
                  />
                </View>
              ) : null}
            </View>
          ))}
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  emptyText: { fontSize: font.body, color: colors.ink },
  chip: {
    fontSize: font.tiny,
    fontWeight: "600",
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
  },
  chipPublished: { backgroundColor: "#e7f6f0", color: colors.teal600 },
  chipMuted: { backgroundColor: colors.surface2, color: colors.muted },
  row: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
  },
  rowTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space(2) },
  rowTitle: { fontSize: font.body, fontWeight: "700", color: colors.ink, flexShrink: 1 },
  rowMeta: { fontSize: font.tiny, color: colors.muted, marginTop: space(1) },
  rowTags: { flexDirection: "row", flexWrap: "wrap", gap: space(2), marginTop: space(2) },
  tag: {
    fontSize: font.tiny,
    color: colors.muted,
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    paddingHorizontal: space(2),
    paddingVertical: 2,
    overflow: "hidden",
  },
});
