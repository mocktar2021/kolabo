import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/dates";
import { earningRowMatches, type EarningKind, type Earnings, type EarningPayment } from "../lib/earningsTypes";
import { Banner, GhostButton, Hint, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

function amount(value: number, currency: string, locale: string): string {
  return `${value.toLocaleString(locale)} ${currency}`;
}

function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const tone =
    status === "released"
      ? { bg: "#e7f6f0", fg: colors.teal600 }
      : status === "disputed"
        ? { bg: "#fdecec", fg: colors.danger }
        : { bg: colors.surface2, fg: colors.muted };
  return (
    <Text style={[styles.chip, { backgroundColor: tone.bg, color: tone.fg }]}>
      {t(`escrow.status_${status}`, { defaultValue: status })}
    </Text>
  );
}

function Tile({
  label,
  hint,
  value,
  active,
  onPress,
}: {
  label: string;
  hint: string;
  value: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable style={[styles.tile, active && styles.tileActive]} onPress={onPress}>
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={styles.tileValue}>{value}</Text>
      <Text style={styles.tileHint}>{hint}</Text>
    </Pressable>
  );
}

export default function EarningsScreen({ navigation }: AppScreenProps<"Earnings">) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [data, setData] = useState<Earnings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pick, setPick] = useState<{ kind: EarningKind; currency: string } | null>(null);

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      setData(await api<Earnings>("/payments/earnings", { token }));
      setError(null);
    } catch {
      setError(t("earn.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const currencies = useMemo(() => {
    if (!data) return [];
    return Array.from(
      new Set([...Object.keys(data.earned), ...Object.keys(data.pending), ...Object.keys(data.disputed)])
    ).sort();
  }, [data]);

  const payments: EarningPayment[] = data?.payments ?? [];
  const shown = pick
    ? payments.filter((p) => p.currency === pick.currency && earningRowMatches(p, pick.kind))
    : payments;

  const toggle = (kind: EarningKind, currency: string) =>
    setPick((cur) => (cur && cur.kind === kind && cur.currency === currency ? null : { kind, currency }));

  const nothing = !loading && currencies.length === 0 && payments.length === 0;

  return (
    <Screen
      loading={loading}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
      <Title>{t("earn.title")}</Title>
      <Subtitle>{t("earn.sub")}</Subtitle>

      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}

      {loading ? null : nothing ? (
        <>
          <Text style={{ color: colors.ink, fontSize: font.body }}>{t("earn.empty")}</Text>
          <Hint>{t("earn.emptyHint")}</Hint>
        </>
      ) : (
        <>
          {currencies.map((currency) => (
            <View key={currency} style={{ marginBottom: space(2) }}>
              {currencies.length > 1 ? (
                <Text style={styles.currencyGroup}>{t("earn.currencyGroup", { currency })}</Text>
              ) : null}
              <View style={styles.tiles}>
                <Tile
                  label={t("earn.earned")}
                  hint={t("earn.earnedHint")}
                  value={amount(data?.earned[currency] ?? 0, currency, i18n.language)}
                  active={pick?.kind === "earned" && pick?.currency === currency}
                  onPress={() => toggle("earned", currency)}
                />
                <Tile
                  label={t("earn.pending")}
                  hint={t("earn.pendingHint")}
                  value={amount(data?.pending[currency] ?? 0, currency, i18n.language)}
                  active={pick?.kind === "pending" && pick?.currency === currency}
                  onPress={() => toggle("pending", currency)}
                />
                <Tile
                  label={t("earn.disputed")}
                  hint={t("earn.disputedHint")}
                  value={amount(data?.disputed[currency] ?? 0, currency, i18n.language)}
                  active={pick?.kind === "disputed" && pick?.currency === currency}
                  onPress={() => toggle("disputed", currency)}
                />
              </View>
            </View>
          ))}

          <Hint>{t("earn.commission")}</Hint>
          {currencies.length > 1 ? <Hint>{t("earn.currencyRule")}</Hint> : null}

          <Text style={styles.statementTitle}>{t("earn.statement")}</Text>
          {pick ? (
            <Text style={styles.showing}>
              {t("earn.showingKind", { label: t(`earn.${pick.kind}`), currency: pick.currency })}{" "}
              <Text style={styles.showAll} onPress={() => setPick(null)}>
                {t("earn.showAll")}
              </Text>
            </Text>
          ) : null}

          {shown.length === 0 ? (
            <Hint>{t("earn.empty")}</Hint>
          ) : (
            <View style={{ gap: space(2) }}>
              {shown.map((row) => (
                <View key={row.escrow_id} style={styles.row}>
                  <View style={styles.rowTop}>
                    <Text
                      style={styles.campaign}
                      onPress={() => navigation.navigate("ContractDetail", { id: row.contract_id })}
                    >
                      {row.campaign_title || t("earn.untitled")}
                    </Text>
                    <StatusChip status={row.status} />
                  </View>
                  <Text style={styles.sub}>
                    {row.counterparty_name || t("earn.unknownBrand")}
                    {row.date ? ` · ${formatDate(row.date, i18n.language)}` : ` · ${t("earn.noDate")}`}
                  </Text>
                  <View style={styles.amounts}>
                    <Text style={styles.amtMuted}>
                      {t("earn.colGross")} {amount(row.gross, row.currency, i18n.language)}
                    </Text>
                    <Text style={styles.amtMuted}>
                      {t("earn.colCommission")} -{amount(row.commission, row.currency, i18n.language)}
                    </Text>
                    <Text style={styles.amtNet}>
                      {t("earn.colNet")} {amount(row.net, row.currency, i18n.language)}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
          )}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  chip: {
    fontSize: font.tiny,
    fontWeight: "600",
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
  },
  tiles: { gap: space(2) },
  tile: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(4),
  },
  tileActive: { borderColor: colors.teal600, backgroundColor: colors.surface2 },
  tileLabel: { fontSize: font.tiny, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  tileValue: { fontSize: 24, fontWeight: "700", color: colors.ink, marginTop: 4 },
  tileHint: { fontSize: font.tiny, color: colors.muted, marginTop: 6 },
  currencyGroup: { fontSize: font.h2, fontWeight: "700", color: colors.ink, marginBottom: space(2) },
  statementTitle: { fontSize: font.h2, fontWeight: "700", color: colors.ink, marginTop: space(4), marginBottom: space(2) },
  showing: { fontSize: font.small, color: colors.muted, marginBottom: space(2) },
  showAll: { color: colors.teal600, fontWeight: "700" },
  row: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
  },
  rowTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space(2) },
  campaign: { fontSize: font.body, fontWeight: "700", color: colors.teal600, flexShrink: 1 },
  sub: { fontSize: font.tiny, color: colors.muted, marginTop: 3 },
  amounts: { flexDirection: "row", flexWrap: "wrap", gap: space(3), marginTop: space(2) },
  amtMuted: { fontSize: font.small, color: colors.muted },
  amtNet: { fontSize: font.small, fontWeight: "700", color: colors.ink },
});
