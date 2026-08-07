import { useState } from "react";
import { View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { useAuth } from "../../lib/auth";
import { NOTE_MAX_LENGTH, type OpenBrief } from "../../lib/boardTypes";
import { Banner, ChoiceGroup, Field, PrimaryButton, type Choice } from "../ui";
import { space } from "../../theme";

const CURRENCIES = ["XOF", "XAF", "GHS", "NGN"];

/* An application IS a proposal: the same rate, currency, timeline and optional
   note an invited creator sends, landing on the same version chain the brand
   answers from its campaign. Defaults the currency to the brief's own — a
   chain priced in two currencies is two negotiations pretending to be one. */
export function ApplyForm({ brief, onApplied }: { brief: OpenBrief; onApplied: () => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rate, setRate] = useState("");
  const [currency, setCurrency] = useState(brief.budget_currency ?? CURRENCIES[0]);
  const [days, setDays] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSend = rate !== "" && days !== "";
  const currencyOptions: Choice[] = CURRENCIES.map((c) => ({ value: c, label: c }));

  async function submit() {
    if (!canSend) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${brief.id}/apply`, {
        method: "POST",
        token,
        body: {
          rate_amount: Number(rate),
          rate_currency: currency,
          timeline_days: Number(days),
          note: note.trim() || null,
        },
      });
      onApplied();
    } catch (e) {
      setError(errorText(e, t));
      setBusy(false);
    }
  }

  return (
    <View style={{ marginTop: space(3) }}>
      {error ? <Banner kind="error">{error}</Banner> : null}
      <Field
        label={t("board.applyRate")}
        value={rate}
        onChangeText={(v) => setRate(v.replace(/\D/g, ""))}
        keyboardType="number-pad"
        placeholder="50000"
      />
      <Field
        label={t("board.applyDays")}
        value={days}
        onChangeText={(v) => setDays(v.replace(/\D/g, ""))}
        keyboardType="number-pad"
        placeholder="7"
      />
      <ChoiceGroup options={currencyOptions} value={currency} onChange={setCurrency} />
      <View style={{ height: space(3) }} />
      <Field
        label={t("board.applyNote")}
        value={note}
        onChangeText={setNote}
        multiline
        numberOfLines={3}
        maxLength={NOTE_MAX_LENGTH}
        placeholder={t("board.applyNotePlaceholder")}
      />
      <PrimaryButton title={busy ? "…" : t("board.applySend")} onPress={submit} loading={busy} disabled={!canSend} />
    </View>
  );
}
