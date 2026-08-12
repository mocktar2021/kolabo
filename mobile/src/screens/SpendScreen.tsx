import { useCallback, useEffect, useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/dates";
import { formatAmount as amount } from "../lib/money";
import type { Spend, SpendPayment } from "../lib/spendTypes";
import { Banner, GhostButton, Hint, Screen, Subtitle } from "../components/ui";
import { colors, family, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const tone =
    status === "released"
      ? { bg: "#e7f6f0", fg: colors.teal600 }
      : status === "disputed"
        ? { bg: "#fdecec", fg: colors.danger }
        : status === "refunded"
          ? { bg: colors.surface2, fg: colors.indigo }
          : { bg: colors.surface2, fg: colors.muted };
  return (
    <Text style={[styles.chip, { backgroundColor: tone.bg, color: tone.fg }]}>
      {t(`escrow.status_${status}`, { defaultValue: status })}
    </Text>
  );
}

function Tile({ label, hint, value }: { label: string; hint: string; value: string }) {
  return (
    <View style={styles.tile}>
      <Text style={styles.tileLabel}>{label}</Text>
      <Text style={styles.tileValue}>{value}</Text>
      <Text style={styles.tileHint}>{hint}</Text>
    </View>
  );
}

export default function SpendScreen({ navigation }: AppScreenProps<"Spend">) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [data, setData] = useState<Spend | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      setData(await api<Spend>("/payments/spend", { token }));
      setError(null);
    } catch {
      setError(t("spend.loadFailed"));
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
      new Set([
        ...Object.keys(data.spent),
        ...Object.keys(data.pending),
        ...Object.keys(data.disputed),
        ...Object.keys(data.refunded),
      ])
    ).sort();
  }, [data]);

  const payments: SpendPayment[] = data?.payments ?? [];
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
      <Subtitle>{t("spend.sub")}</Subtitle>

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
          <Text style={{ fontFamily: family.body, color: colors.ink, fontSize: font.body }}>{t("spend.empty")}</Text>
          <Hint>{t("spend.emptyHint")}</Hint>
        </>
      ) : (
        <>
          {currencies.map((currency) => (
            <View key={currency} style={{ marginBottom: space(2) }}>
              {currencies.length > 1 ? (
                <Text style={styles.currencyGroup}>{t("spend.currencyGroup", { currency })}</Text>
              ) : null}
              <View style={{ gap: space(2) }}>
                <Tile label={t("spend.spent")} hint={t("spend.spentHint")} value={amount(data?.spent[currency] ?? 0, currency, i18n.language)} />
                <Tile label={t("spend.pending")} hint={t("spend.pendingHint")} value={amount(data?.pending[currency] ?? 0, currency, i18n.language)} />
                <Tile label={t("spend.disputed")} hint={t("spend.disputedHint")} value={amount(data?.disputed[currency] ?? 0, currency, i18n.language)} />
                <Tile label={t("spend.refunded")} hint={t("spend.refundedHint")} value={amount(data?.refunded[currency] ?? 0, currency, i18n.language)} />
              </View>
            </View>
          ))}

          <Hint>{t("spend.gross")}</Hint>
          {currencies.length > 1 ? <Hint>{t("spend.currencyRule")}</Hint> : null}

          <Text style={styles.statementTitle}>{t("spend.statement")}</Text>
          {payments.length === 0 ? (
            <Hint>{t("spend.empty")}</Hint>
          ) : (
            <View style={{ gap: space(2) }}>
              {payments.map((row) => (
                <View key={row.escrow_id} style={styles.row}>
                  <View style={styles.rowTop}>
                    <Text
                      style={styles.campaign}
                      onPress={() => navigation.navigate("ContractDetail", { id: row.contract_id })}
                    >
                      {row.campaign_title || t("spend.untitled")}
                    </Text>
                    <StatusChip status={row.status} />
                  </View>
                  <Text style={styles.sub}>
                    {row.counterparty_name || t("spend.unknownCreator")}
                    {row.date ? ` · ${formatDate(row.date, i18n.language)}` : ` · ${t("spend.noDate")}`}
                  </Text>
                  <Text style={styles.amount}>
                    {amount(row.amount, row.currency, i18n.language)}
                    {row.refunded_amount > 0
                      ? ` · ${t("spend.rowRefunded", { amount: amount(row.refunded_amount, row.currency, i18n.language) })}`
                      : ""}
                  </Text>
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
    fontFamily: family.bodySemi,
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
  },
  tile: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(4),
  },
  tileLabel: { fontSize: font.tiny, fontFamily: family.bodyBold, color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  tileValue: { fontSize: 24, fontFamily: family.display, color: colors.ink, marginTop: 4 },
  tileHint: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 6 },
  currencyGroup: { fontSize: font.h2, fontFamily: family.display, color: colors.ink, marginBottom: space(2) },
  statementTitle: { fontSize: font.h2, fontFamily: family.display, color: colors.ink, marginTop: space(4), marginBottom: space(2) },
  row: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
  },
  rowTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space(2) },
  campaign: { fontSize: font.body, fontFamily: family.bodyBold, color: colors.teal600, flexShrink: 1 },
  sub: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 3 },
  amount: { fontSize: font.small, color: colors.ink, marginTop: space(2), fontFamily: family.bodySemi },
});
