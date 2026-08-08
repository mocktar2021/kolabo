import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/dates";
import type { Campaign } from "../lib/campaignTypes";
import { campaignIsCompleted, partitionByCompletion, type CompletableContract } from "../lib/lifecycle";
import { ListFilter, ListTabs, type FilterOption, type Tab } from "../components/lists";
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
  const [tab, setTab] = useState<Tab>("active");
  const [statusFilter, setStatusFilter] = useState("");
  /* The caller's contracts, fetched ONLY to work out which campaigns are
     finished — a campaign has no completed status of its own; what ends it is
     the work underneath it ending. Failing here is not worth an error state:
     it costs the Completed shelf its accuracy and leaves the rest working. */
  const [contracts, setContracts] = useState<CompletableContract[]>([]);

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      setCampaigns(await api<Campaign[]>("/campaigns/mine", { token }));
      setError(null);
    } catch (e) {
      setError(errorText(e, t));
    }
    api<CompletableContract[]>("/contracts/mine", { token })
      .then(setContracts)
      .catch(() => setContracts([]));
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

  const { active, completed } = partitionByCompletion(campaigns ?? [], (c) =>
    campaignIsCompleted(c, contracts)
  );
  const inTab = tab === "completed" ? completed : active;
  const statusOptions: FilterOption[] = Array.from(new Set(inTab.map((c) => c.status))).map(
    (s) => ({ value: s, label: t(`campaign.status_${s}`, { defaultValue: s }) })
  );
  const shown = statusFilter ? inTab.filter((c) => c.status === statusFilter) : inTab;

  function selectTab(next: Tab) {
    setTab(next);
    setStatusFilter("");
  }

  return (
    <Screen
      loading={campaigns === null && !error}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
      <Title>{t("campaign.listTitle")}</Title>
      <Subtitle>{t("campaign.listSub")}</Subtitle>

      <View style={{ marginBottom: space(4) }}>
        <PrimaryButton title={t("campaign.new")} onPress={() => navigation.navigate("CampaignNew")} />
      </View>

      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}

      {!loading && !empty ? (
        <View style={{ marginBottom: space(3) }}>
          <ListTabs
            active={tab}
            activeCount={active.length}
            completedCount={completed.length}
            onChange={selectTab}
          />
          <ListFilter options={statusOptions} value={statusFilter} onChange={setStatusFilter} />
        </View>
      ) : null}

      {loading ? null : empty ? (
        <>
          <Text style={styles.emptyText}>{t("campaign.listEmpty")}</Text>
          <Hint>{t("campaign.listEmptyHint")}</Hint>
        </>
      ) : shown.length === 0 ? (
        <Hint>
          {inTab.length === 0
            ? t(tab === "completed" ? "lf.noneCompleted" : "lf.noneActive")
            : t("lf.none")}
        </Hint>
      ) : (
        <View style={{ gap: space(2) }}>
          {shown.map((c) => (
            <Pressable
              key={c.id}
              onPress={() => navigation.navigate("CampaignDetail", { id: c.id })}
              style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surface }]}
            >
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
            </Pressable>
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
