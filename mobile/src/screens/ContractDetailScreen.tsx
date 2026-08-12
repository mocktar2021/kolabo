import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { formatAmount } from "../lib/money";
import { useAuth } from "../lib/auth";
import type { ContractDetail, Escrow } from "../lib/contractTypes";
import { openDisputeFor, type Dispute } from "../lib/disputeTypes";
import { DeliverablesPanel } from "../components/contracts/DeliverablesPanel";
import { RaiseDisputeForm } from "../components/contracts/RaiseDisputeForm";
import { Banner, Card, Field, GhostButton, Hint, PrimaryButton, Screen, SectionTitle, Subtitle } from "../components/ui";
import { colors, family, font, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

function Row({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, ok && { color: colors.teal600, fontFamily: family.bodyBold }]}>{value}</Text>
    </View>
  );
}

export default function ContractDetailScreen({ navigation, route }: AppScreenProps<"ContractDetail">) {
  const { t, i18n } = useTranslation();
  const { userId, token } = useAuth();
  const { id } = route.params;

  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [signature, setSignature] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [raising, setRaising] = useState(false);

  const loadEscrow = useCallback(
    async (contractId: string) => {
      try {
        setEscrow(await api<Escrow>(`/payments/escrow/by-contract/${contractId}`, { token }));
        // The caller's cases in one request; the open one on this escrow (if
        // any) is found client-side, exactly as the web contract page does it.
        try {
          setDisputes(await api<Dispute[]>("/payments/disputes/mine", { token }));
        } catch {
          setDisputes([]);
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setEscrow(null);
      }
    },
    [token]
  );

  const [refreshing, setRefreshing] = useState(false);
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
  const openDispute = escrow ? openDisputeFor(disputes, escrow.id) : null;

  return (
    <Screen
      loading={loading}
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

      {loading ? null : !contract ? (
        <Hint>{t("contract.listEmpty")}</Hint>
      ) : (
        <>
          <Subtitle>
            {t(`contract.status_${contract.status}`, { defaultValue: contract.status })}
          </Subtitle>

          <Card>
            <Row label={t("contract.rate")} value={formatAmount(contract.rate_amount, contract.rate_currency, i18n.language)} />
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
                    <Row label={t("contract.amount")} value={formatAmount(escrow.amount, escrow.currency, i18n.language)} />
                    {escrow.commission_amount !== null ? (
                      <Row
                        label={t("contract.commission")}
                        value={formatAmount(escrow.commission_amount, escrow.currency, i18n.language)}
                      />
                    ) : null}
                    {/* No standalone release button (D2): confirming delivery is
                        approving the open submission, which happens in the
                        deliverables panel below. */}
                    {/* Either party can report a problem while the money is
                        held: it freezes the escrow and starts the response
                        window. Said before the click inside the form. */}
                    {escrow.status === "held" ? (
                      raising ? (
                        <RaiseDisputeForm
                          escrowId={escrow.id}
                          onSubmitted={async () => {
                            setRaising(false);
                            await load();
                          }}
                          onCancel={() => setRaising(false)}
                        />
                      ) : (
                        <View style={{ marginTop: space(2) }}>
                          <GhostButton title={t("dispute.open")} onPress={() => setRaising(true)} />
                        </View>
                      )
                    ) : null}
                    {escrow.status === "released" ? <Banner kind="success">{t("contract.released")}</Banner> : null}
                    {escrow.status === "refunded" ? <Banner kind="info">{t("contract.refunded")}</Banner> : null}
                    {escrow.status === "disputed" ? (
                      <>
                        <Banner kind="info">{t("contract.disputed")}</Banner>
                        {openDispute ? (
                          <GhostButton
                            title={t("dispute.view")}
                            onPress={() => navigation.navigate("DisputeDetail", { id: openDispute.id })}
                          />
                        ) : null}
                      </>
                    ) : null}
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
  /* The label owns the leftover width and may wrap; the value keeps its
     intrinsic size — so neither can ever clip the other's tail again. */
  rowLabel: { flex: 1, paddingRight: space(2), fontFamily: family.body, fontSize: font.small, color: colors.muted },
  rowValue: { flexShrink: 0, fontFamily: family.body, fontSize: font.small, color: colors.ink },
  body: { fontFamily: family.body, fontSize: font.small,
    color: colors.ink,
    backgroundColor: colors.surface,
    padding: space(3),
    borderRadius: 8,
    lineHeight: 20,
  },
});
