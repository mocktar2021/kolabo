import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/dates";
import { formatAmount as amount } from "../lib/money";
import { getPayoutMethod, payoutModeLabel, type PayoutMethod } from "../lib/checkout";
import { earningRowMatches, type EarningKind, type Earnings, type EarningPayment } from "../lib/earningsTypes";
/* Side-effect import: registers the payout.* copy used by the card below. */
import "../lib/parityStrings";
import { Banner, Card, GhostButton, Hint, PrimaryButton, Screen, SectionTitle, Subtitle } from "../components/ui";
import { colors, family, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

/* Where the money lands, as this screen is allowed to know it.

   THERE IS NO ENDPOINT THAT LISTS PAYOUTS. The Payout rows exist
   (payments/gateway_models.Payout) and carry pending / sent / failed /
   awaiting_method, but nothing publishes them: GET /payments/earnings answers
   about ESCROWS, and the only payout route a party can read is
   GET /payments/payout-method — which is exactly what web's earnings header
   uses. So this screen reports the state it can prove rather than inventing a
   list: whether a wallet is on file, and, when one is not, that released money
   has nowhere to go.

   `known` is the third state and it matters. A failed read of the wallet is
   not the same fact as "no wallet", and treating it as one would tell a
   creator with a perfectly good wallet that their money is stranded. */
type Wallet = { known: boolean; method: PayoutMethod | null };

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
  const [wallet, setWallet] = useState<Wallet>({ known: false, method: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pick, setPick] = useState<{ kind: EarningKind; currency: string } | null>(null);

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      /* Both in one trip. The wallet read resolves either way — a failure is
         answered as "we do not know" rather than thrown — so a payout-method
         outage never costs a creator the statement they came here for. */
      const [earnings, nextWallet] = await Promise.all([
        api<Earnings>("/payments/earnings", { token }),
        getPayoutMethod(token).then(
          (method): Wallet => ({ known: true, method }),
          (): Wallet => ({ known: false, method: null })
        ),
      ]);
      setData(earnings);
      setWallet(nextWallet);
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

  /* What has actually been released, one line per currency and never a sum
     across them — the rule the rest of this screen is built on. */
  const earnedTotals: Record<string, number> = data?.earned ?? {};
  const released = Object.entries(earnedTotals).filter(([, value]) => value > 0);
  /* Read once into a local so the narrowing below survives: null means "asked
     and there is none", which is only actionable together with `known`. */
  const saved = wallet.method;
  /* The awaiting_method state, derived from the two facts the client can see:
     money has been released to this creator, and we hold no wallet to send it
     to. That is precisely the condition payouts.disburse writes the row for. */
  const awaitingMethod = wallet.known && !saved && released.length > 0;

  return (
    <Screen
      loading={loading}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
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
          <Text style={{ fontFamily: family.body, color: colors.ink, fontSize: font.body }}>{t("earn.empty")}</Text>
          <Hint>{t("earn.emptyHint")}</Hint>
        </>
      ) : (
        <>
          {/* ABOVE the tiles, not below them. "Where does this land" is the
              first question on this screen, and a creator whose releases are
              stranded for want of a wallet must not have to scroll past three
              stacked tiles to find that out. Web puts the same route in its
              page header for the same reason. */}
          <Card>
            <SectionTitle>{t("payout.title")}</SectionTitle>
            {saved ? (
              <>
                <Text style={styles.walletLabel}>{t("payout.walletSaved")}</Text>
                <Text style={styles.wallet}>
                  {payoutModeLabel(saved.mode)} · {saved.phone_masked}
                </Text>
                <Hint>{t("payout.hint")}</Hint>
                <View style={{ height: space(2) }} />
                <GhostButton
                  title={t("payout.change")}
                  onPress={() => navigation.navigate("PayoutMethod")}
                />
              </>
            ) : awaitingMethod ? (
              <>
                {/* Said plainly and in this order: it is yours, here is how
                    much, here is why it has not arrived, here is the way to
                    fix it. The amounts are the released totals, one per
                    currency, because none of it has been sent anywhere. */}
                <Text style={styles.awaitingTitle}>{t("payout.awaitingTitle")}</Text>
                <Text style={styles.walletLabel}>{t("payout.releasedLabel")}</Text>
                {released.map(([currency, value]) => (
                  <Text key={currency} style={styles.awaitingAmount}>
                    {amount(value, currency, i18n.language)}
                  </Text>
                ))}
                <Hint>{t("payout.awaiting")}</Hint>
                <View style={{ height: space(2) }} />
                <PrimaryButton
                  title={t("payout.add")}
                  onPress={() => navigation.navigate("PayoutMethod")}
                />
              </>
            ) : (
              <>
                {/* Nothing released yet, or the wallet read failed. Neither is
                    a stranded payment, so neither gets the alarm — but both
                    get the route, because setting a wallet up BEFORE the first
                    release is the version of this that costs nobody anything. */}
                <Hint>{wallet.known ? t("payout.none") : t("payout.unknown")}</Hint>
                <View style={{ height: space(2) }} />
                <GhostButton
                  title={t("payout.add")}
                  onPress={() => navigation.navigate("PayoutMethod")}
                />
              </>
            )}
          </Card>

          <View style={{ height: space(4) }} />

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
              {/* The WHOLE row opens the contract, exactly like the web
                  statement and the contracts list. It used to be only the
                  title text — a one-line tap target with no pressed state,
                  which reads as a dead link on a phone. */}
              {shown.map((row) => (
                <Pressable
                  key={row.escrow_id}
                  style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surface }]}
                  onPress={() => navigation.navigate("ContractDetail", { id: row.contract_id })}
                >
                  <View style={styles.rowTop}>
                    <Text style={styles.campaign}>{row.campaign_title || t("earn.untitled")}</Text>
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
                </Pressable>
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
  tiles: { gap: space(2) },
  tile: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(4),
  },
  tileActive: { borderColor: colors.teal600, backgroundColor: colors.surface2 },
  tileLabel: { fontSize: font.tiny, fontFamily: family.bodyBold, color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  tileValue: { fontSize: 24, fontFamily: family.display, color: colors.ink, marginTop: 4 },
  tileHint: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 6 },
  walletLabel: { fontSize: font.tiny, fontFamily: family.bodyBold, color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  wallet: { fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink, marginTop: 4 },
  awaitingTitle: { fontSize: font.body, fontFamily: family.bodyBold, color: colors.ink, marginBottom: space(2) },
  awaitingAmount: { fontSize: 22, fontFamily: family.display, color: colors.ink, marginTop: 2 },
  currencyGroup: { fontSize: font.h2, fontFamily: family.display, color: colors.ink, marginBottom: space(2) },
  statementTitle: { fontSize: font.h2, fontFamily: family.display, color: colors.ink, marginTop: space(4), marginBottom: space(2) },
  showing: { fontFamily: family.body, fontSize: font.small, color: colors.muted, marginBottom: space(2) },
  showAll: { color: colors.teal600, fontFamily: family.bodyBold },
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
  amounts: { flexDirection: "row", flexWrap: "wrap", gap: space(3), marginTop: space(2) },
  amtMuted: { fontFamily: family.body, fontSize: font.small, color: colors.muted },
  amtNet: { fontSize: font.small, fontFamily: family.bodyBold, color: colors.ink },
});
