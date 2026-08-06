import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import type { ContractDetail, Escrow } from "../lib/contractTypes";
import { DeliverablesPanel } from "../components/contracts/DeliverablesPanel";
import { Banner, Card, Field, GhostButton, Hint, PrimaryButton, Screen, SectionTitle, Subtitle, Title } from "../components/ui";
import { colors, font, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

function Row({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, ok && { color: colors.teal600, fontWeight: "700" }]}>{value}</Text>
    </View>
  );
}

export default function ContractDetailScreen({ navigation, route }: AppScreenProps<"ContractDetail">) {
  const { t } = useTranslation();
  const { userId, token } = useAuth();
  const { id } = route.params;

  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [signature, setSignature] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadEscrow = useCallback(
    async (contractId: string) => {
      try {
        setEscrow(await api<Escrow>(`/payments/escrow/by-contract/${contractId}`, { token }));
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setEscrow(null);
      }
    },
    [token]
  );

  const load = useCallback(async () => {
    try {
      const c = await api<ContractDetail>(`/contracts/${id}`, { token });
      setContract(c);
      if (c.fully_signed) await loadEscrow(c.id);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setLoading(false);
    }
  }, [id, token, loadEscrow, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  const isBusiness = !!contract && userId === contract.business_user_id;
  const alreadySigned = !!contract && (isBusiness ? contract.business_signed : contract.influencer_signed);

  return (
    <Screen>
      <View style={{ marginBottom: space(2) }}>
        <GhostButton title={t("common.back")} onPress={() => navigation.goBack()} />
      </View>

      {error ? <Banner kind="error">{error}</Banner> : null}

      {loading ? null : !contract ? (
        <Hint>{t("contract.listEmpty")}</Hint>
      ) : (
        <>
          <Title>{t("contract.title")}</Title>
          <Subtitle>
            {t(`contract.status_${contract.status}`, { defaultValue: contract.status })}
          </Subtitle>

          <Card>
            <Row label={t("contract.rate")} value={`${contract.rate_amount} ${contract.rate_currency}`} />
            <Row label={t("contract.timeline")} value={`${contract.timeline_days} ${t("contract.days")}`} />
            <Row
              label={t("contract.businessSigned")}
              value={contract.business_signed ? t("contract.yes") : t("contract.no")}
              ok={contract.business_signed}
            />
            <Row
              label={t("contract.creatorSigned")}
              value={contract.influencer_signed ? t("contract.yes") : t("contract.no")}
              ok={contract.influencer_signed}
            />
          </Card>

          <View style={{ height: space(4) }} />
          <Card>
            <SectionTitle>{t("contract.document")}</SectionTitle>
            <Text style={styles.body}>{contract.body}</Text>
          </Card>

          {!contract.fully_signed ? (
            <>
              <View style={{ height: space(4) }} />
              <Card>
                <SectionTitle>{t("contract.signHeading")}</SectionTitle>
                {alreadySigned ? (
                  <Banner kind="info">{t("contract.waitingOther")}</Banner>
                ) : (
                  <>
                    <Field
                      label={t("contract.typeName")}
                      value={signature}
                      onChangeText={setSignature}
                      placeholder={t("contract.namePlaceholder")}
                    />
                    <PrimaryButton
                      title={busy ? "…" : t("contract.sign")}
                      onPress={() =>
                        act(() =>
                          api(`/contracts/${contract.id}/sign`, { method: "POST", token, body: { signature } })
                        )
                      }
                      loading={busy}
                      disabled={!signature.trim()}
                    />
                  </>
                )}
              </Card>
            </>
          ) : null}

          {contract.fully_signed ? (
            <>
              <View style={{ height: space(4) }} />
              <Card>
                <SectionTitle>{t("contract.payment")}</SectionTitle>
                {!escrow ? (
                  isBusiness ? (
                    <>
                      <Hint>{t("contract.fundHint")}</Hint>
                      <View style={{ height: space(2) }} />
                      <PrimaryButton
                        title={busy ? "…" : t("contract.fund")}
                        onPress={() =>
                          act(() =>
                            api("/payments/escrow/fund", {
                              method: "POST",
                              token,
                              body: { contract_id: contract.id },
                            })
                          )
                        }
                        loading={busy}
                      />
                    </>
                  ) : (
                    <Banner kind="info">{t("contract.awaitingFunding")}</Banner>
                  )
                ) : (
                  <>
                    <Row
                      label={t("contract.escrowStatus")}
                      value={t(`escrow.status_${escrow.status}`, { defaultValue: escrow.status })}
                      ok={escrow.status === "released"}
                    />
                    <Row label={t("contract.amount")} value={`${escrow.amount} ${escrow.currency}`} />
                    {escrow.commission_amount !== null ? (
                      <Row label={t("contract.commission")} value={`${escrow.commission_amount} ${escrow.currency}`} />
                    ) : null}
                    {/* No standalone release button (D2): confirming delivery is
                        approving the open submission, which happens in the
                        deliverables panel below. */}
                    {escrow.status === "released" ? <Banner kind="success">{t("contract.released")}</Banner> : null}
                    {escrow.status === "refunded" ? <Banner kind="info">{t("contract.refunded")}</Banner> : null}
                    {escrow.status === "disputed" ? <Banner kind="info">{t("contract.disputed")}</Banner> : null}
                  </>
                )}
              </Card>

              <View style={{ height: space(4) }} />
              <Card>
                <DeliverablesPanel
                  contractId={contract.id}
                  isBusiness={isBusiness}
                  hasEscrow={!!escrow}
                  escrowHeld={escrow?.status === "held"}
                  onChanged={load}
                />
              </Card>
            </>
          ) : null}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 },
  rowLabel: { fontSize: font.small, color: colors.muted },
  rowValue: { fontSize: font.small, color: colors.ink },
  body: {
    fontSize: font.small,
    color: colors.ink,
    backgroundColor: colors.surface,
    padding: space(3),
    borderRadius: 8,
    lineHeight: 20,
  },
});
