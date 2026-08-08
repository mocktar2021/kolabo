import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/dates";
import type { ContractListItem } from "../lib/contractTypes";
import { contractIsCompleted, partitionByCompletion } from "../lib/lifecycle";
import { ListFilter, ListTabs, type FilterOption, type Tab } from "../components/lists";
import { Banner, GhostButton, Hint, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

export default function ContractsListScreen({ navigation }: AppScreenProps<"Contracts">) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [rows, setRows] = useState<ContractListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("active");
  /* "" is all. Filtered in memory — /contracts/mine returns the whole set
     and it is short at pilot volume. */
  const [statusFilter, setStatusFilter] = useState("");

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    try {
      setRows(await api<ContractListItem[]>("/contracts/mine", { token }));
      setError(null);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const { active, completed } = partitionByCompletion(rows, contractIsCompleted);
  const inTab = tab === "completed" ? completed : active;
  /* Chips from the statuses present IN THIS TAB, labelled with the same key
     the row's pill renders, so a status is worded one way across the screen
     and no chip ever matches zero rows. */
  const statusOptions: FilterOption[] = Array.from(new Set(inTab.map((c) => c.status))).map(
    (s) => ({ value: s, label: t(`contract.status_${s}`, { defaultValue: s }) })
  );
  const shown = statusFilter ? inTab.filter((c) => c.status === statusFilter) : inTab;

  function selectTab(next: Tab) {
    setTab(next);
    setStatusFilter("");
  }

  return (
    <Screen
      loading={loading}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
      <Title>{t("contract.listTitle")}</Title>
      <Subtitle>{t("contract.listSub")}</Subtitle>
      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}

      {!loading && rows.length > 0 ? (
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

      {loading ? null : rows.length === 0 ? (
        <Hint>{t("contract.listEmpty")}</Hint>
      ) : shown.length === 0 ? (
        <Hint>
          {inTab.length === 0
            ? t(tab === "completed" ? "lf.noneCompleted" : "lf.noneActive")
            : t("lf.none")}
        </Hint>
      ) : (
        <View style={{ gap: space(3) }}>
          {shown.map((c) => (
            <Pressable
              key={c.id}
              style={styles.card}
              onPress={() => navigation.navigate("ContractDetail", { id: c.id })}
            >
              <View style={styles.top}>
                <View style={{ flexShrink: 1 }}>
                  <Text style={styles.title}>{c.campaign_title || t("contract.untitled")}</Text>
                  <Text style={styles.party}>{c.counterparty_name || t("contract.party")}</Text>
                </View>
                <View style={{ alignItems: "flex-end", gap: 3 }}>
                  <Text style={[styles.chip, c.fully_signed && styles.chipOk]}>
                    {t(`contract.status_${c.status}`, { defaultValue: c.status })}
                  </Text>
                  {c.escrow_status ? (
                    <Text style={styles.escrow}>
                      {t(`escrow.status_${c.escrow_status}`, { defaultValue: c.escrow_status })}
                    </Text>
                  ) : null}
                </View>
              </View>
              <View style={styles.terms}>
                <Text style={styles.rate}>
                  {c.rate_amount} {c.rate_currency}
                </Text>
                <Text style={styles.muted}>
                  {c.timeline_days} {t("contract.days")}
                </Text>
                <Text style={styles.muted}>{c.language.toUpperCase()}</Text>
                <Text style={styles.muted}>{formatDate(c.created_at, i18n.language)}</Text>
              </View>
            </Pressable>
          ))}
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(4),
  },
  top: { flexDirection: "row", justifyContent: "space-between", gap: space(3) },
  title: { fontSize: font.body, fontWeight: "700", color: colors.ink },
  party: { fontSize: font.small, color: colors.muted, marginTop: 3 },
  chip: {
    fontSize: font.tiny,
    fontWeight: "600",
    color: colors.muted,
    backgroundColor: colors.surface2,
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
  },
  chipOk: { color: colors.teal600 },
  escrow: { fontSize: font.tiny, color: colors.muted },
  terms: { flexDirection: "row", flexWrap: "wrap", gap: space(3), marginTop: space(3) },
  rate: { fontSize: font.small, fontWeight: "700", color: colors.ink },
  muted: { fontSize: font.small, color: colors.muted },
});
