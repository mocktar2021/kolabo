import { useState } from "react";
import { Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, type MediaOut } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { useAuth } from "../../lib/auth";
import {
  DISPUTE_REASONS,
  MAX_STATEMENT_CHARS,
  MIN_STATEMENT_CHARS,
  type DisputeReason,
} from "../../lib/disputeTypes";
import { EvidencePicker } from "../disputes/EvidencePicker";
import { Banner, ChoiceGroup, Field, GhostButton, Hint, PrimaryButton, type Choice } from "../ui";
import { colors, family, font, space } from "../../theme";

/* Reporting a problem, inline on the contract. Raising a dispute freezes the
   money for both sides and hands the other party a 72 h window — the
   consequence is said before the button, not after it, exactly as web does.
   Screenshots ride along as media ids the EvidencePicker has already
   uploaded, so submitting never waits on an upload. */
export function RaiseDisputeForm({
  escrowId,
  onSubmitted,
  onCancel,
}: {
  escrowId: string;
  onSubmitted: () => void | Promise<void>;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const { userId, token } = useAuth();
  const [reason, setReason] = useState<DisputeReason>("not_delivered");
  const [statement, setStatement] = useState("");
  const [evidence, setEvidence] = useState<MediaOut[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const length = statement.trim().length;
  const tooShort = length < MIN_STATEMENT_CHARS;
  const tooLong = length > MAX_STATEMENT_CHARS;

  const reasonOptions: Choice[] = DISPUTE_REASONS.map((r) => ({
    value: r,
    label: t(`dispute.reason_${r}`),
  }));

  async function submit() {
    if (tooShort || tooLong) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/payments/escrow/${escrowId}/dispute`, {
        method: "POST",
        token,
        body: { reason, statement: statement.trim(), media_ids: evidence.map((e) => e.id) },
      });
      await onSubmitted();
    } catch (e) {
      setError(errorText(e, t));
      setBusy(false);
    }
  }

  return (
    <View style={{ marginTop: space(3) }}>
      {error ? <Banner kind="error">{error}</Banner> : null}
      <Text style={{ fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) }}>
        {t("dispute.reason")}
      </Text>
      <ChoiceGroup options={reasonOptions} value={reason} onChange={(v) => setReason(v as DisputeReason)} />
      <View style={{ height: space(3) }} />
      <Field
        label={t("dispute.statement")}
        value={statement}
        onChangeText={setStatement}
        multiline
        numberOfLines={4}
        maxLength={MAX_STATEMENT_CHARS}
        placeholder={t("dispute.statementPlaceholder")}
      />
      {tooShort && length > 0 ? <Hint>{t("dispute.statementTooShort", { n: MIN_STATEMENT_CHARS })}</Hint> : null}
      <View style={{ height: space(2) }} />
      {userId ? <EvidencePicker userId={userId} token={token} value={evidence} onChange={setEvidence} /> : null}
      <Hint>{t("dispute.consequence")}</Hint>
      <View style={{ height: space(2) }} />
      <PrimaryButton title={busy ? "…" : t("dispute.submit")} onPress={submit} loading={busy} disabled={tooShort || tooLong} />
      <View style={{ height: space(2) }} />
      <GhostButton title={t("dispute.cancel")} onPress={onCancel} disabled={busy} />
    </View>
  );
}
