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
/* Side-effect import: registers the undo.* copy for the cancel card below. */
import "../lib/parityStrings";
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
  /* The cancel card's own two pieces of state. Kept apart from the page-level
     error so a refused cancellation does not replace whatever the rest of the
     screen was saying, exactly as web keeps them apart. */
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

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

  /* Calling off a contract that has not yet bound anybody.

     EITHER PARTY, not just the buyer. Nothing is owed in either direction yet,
     and a creator who has realised they cannot deliver should be able to say
     so in the app rather than by not answering — silence is what sends the
     next conversation to WhatsApp and the one after that off-platform for
     good. Until this button existed the phone had no exit at all: a creator
     who had signed had to find a browser or write to support.

     DELIBERATELY NOT THROUGH act(). act() lands its failure in the page-level
     banner at the top of a long contract screen, which on a phone is several
     screens above this card — from the reader's seat the button would have
     done nothing. The refusals go inline, next to the thing that was refused.

     Both refusals arrive with their own code and are already written out in
     both languages (lib/errorMessages.ts), so errorText tells them apart:

       contract_cancel_funded (409)  money is at the provider, which turns
            "should this end" into "who is owed what" — the dispute and refund
            path, which has an audit log and an admin. A cancel button running
            alongside that would be a second, unaudited way for money to stop
            moving, and it would be the one somebody reached for first.
       contract_cancel_signed (400)  both parties put their name to these
            terms. Walking out of an agreement by pressing something is the
            thing a contract exists to prevent.
       contract_already_cancelled (400) a double tap, told plainly rather than
            silently re-notifying the other party. */
  async function cancelContract() {
    if (!contract) return;
    setBusy(true);
    setCancelError(null);
    try {
      await api(`/contracts/${contract.id}/cancel`, { method: "POST", token });
      setConfirmingCancel(false);
      await load();
    } catch (e) {
      setCancelError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  const isBusiness = !!contract && userId === contract.business_user_id;
  const alreadySigned = !!contract && (isBusiness ? contract.business_signed : contract.influencer_signed);
  const openDispute = escrow ? openDisputeFor(disputes, escrow.id) : null;
  /* Offered while the contract binds nobody, mirroring web's placement logic
     and cancellation.py behind it: TWO conditions and not one. A full
     signature closes the door, and so does an escrow, separately. In practice
     they line up today because funding requires a full signature — but they
     are different facts and the one that matters is the money. A cancelled
     contract drops the offer too, rather than leaving a button that answers
     400. */
  const cancellable =
    !!contract && !contract.fully_signed && contract.status !== "cancelled" && !escrow;

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

          {/* Below the signature block on purpose, as on web: signing is what
              this screen is for, and the way out should not sit above the way
              through. */}
          {cancellable ? (
            <>
              <View style={{ height: space(4) }} />
              <Card>
                <SectionTitle>{t("undo.contractTitle")}</SectionTitle>
                {cancelError ? <Banner kind="error">{cancelError}</Banner> : null}
                {!confirmingCancel ? (
                  <>
                    <Hint>{t("undo.contractExplain")}</Hint>
                    <View style={{ height: space(2) }} />
                    {/* TWO TAPS, ALWAYS. This ends an agreement and notifies
                        the other party, and a thumb on a 360 dp screen is not
                        a precise instrument: the first tap only asks. */}
                    <GhostButton
                      title={t("undo.contractCancel")}
                      onPress={() => {
                        setConfirmingCancel(true);
                        setCancelError(null);
                      }}
                      disabled={busy}
                    />
                  </>
                ) : (
                  <>
                    {/* The consequence stated before the tap, not after it:
                        the other party is told, the agreement is over, and
                        working together again means a new proposal. */}
                    <Text style={styles.confirm}>{t("undo.contractConfirm")}</Text>
                    <View style={{ height: space(2) }} />
                    <PrimaryButton
                      title={busy ? "…" : t("undo.contractYes")}
                      onPress={() => void cancelContract()}
                      loading={busy}
                    />
                    <View style={{ height: space(2) }} />
                    <GhostButton
                      title={t("undo.contractNo")}
                      onPress={() => {
                        setConfirmingCancel(false);
                        setCancelError(null);
                      }}
                      disabled={busy}
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
                      {/* Funding is no longer one call that hands back a funded
                          escrow. The money moves on the payer's handset at the
                          gateway and the escrow exists only once it lands, so
                          this button opens that conversation rather than
                          finishing it. POST /payments/escrow/fund is still
                          there but refuses (escrow_use_checkout) the moment a
                          live gateway is configured — which is every
                          deployment that takes real money. */}
                      <PrimaryButton
                        title={t("contract.fund")}
                        onPress={() => navigation.navigate("Checkout", { contractId: contract.id })}
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
  /* The confirmation sentence is not a Hint: it is the last thing read before
     an irreversible tap, so it gets body ink and body size rather than the
     muted 12 pt every other aside on this screen uses. */
  confirm: { fontFamily: family.body, fontSize: font.small, color: colors.ink, lineHeight: 20 },
});
