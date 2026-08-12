import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { useAuth } from "../../lib/auth";
import {
  targetingBody,
  targetingOf,
  type CampaignDetailData,
  type Deliverable,
  type Targeting,
} from "../../lib/campaignTypes";
import { DeliverableRows } from "./DeliverableRows";
import { TargetingFields } from "./TargetingFields";
import { Banner, ChoiceGroup, Field, GhostButton, Hint, PrimaryButton } from "../ui";
import { colors, family, font, space } from "../../theme";

const CURRENCIES = ["XOF", "XAF", "GHS", "NGN"];
const MAX_DESCRIPTION_LENGTH = 5000;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/* Correcting a brief in place, within what the people looking at it allow.

   THE RULE IS THE BACKEND'S (campaigns/editing.py holds the authority; this
   form mirrors it so the buyer meets it as a read-only row rather than a
   400). Title and description are description, not terms — they never lock.
   Budget, currency, deliverables and deadline are what a creator PRICES
   AGAINST, and they lock the moment a proposal exists on a published
   campaign. Targeting and is_open are NOT terms — nobody prices a brief
   against who else the brand hoped to hear from — so they stay editable
   throughout, which is why TargetingFields sits outside the lock.

   Only what actually changed goes in the PATCH: it is exclude_unset
   server-side, and posting the whole form back would hand the lock check a
   budget to compare when the buyer only fixed a typo in the title. */
export function CampaignEditForm({ campaign, locked, onSaved, onClose }: {
  campaign: CampaignDetailData;
  locked: boolean;
  onSaved: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { token } = useAuth();

  const [title, setTitle] = useState(campaign.title);
  const [description, setDescription] = useState(campaign.description ?? "");
  const [budget, setBudget] = useState(campaign.budget_amount ? String(campaign.budget_amount) : "");
  const [currency, setCurrency] = useState(campaign.budget_currency ?? "XOF");
  const [deadline, setDeadline] = useState(campaign.deadline ?? "");
  const [deliverables, setDeliverables] = useState<Deliverable[]>(campaign.deliverables);
  const [targeting, setTargeting] = useState<Targeting>(targetingOf(campaign));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const badDeadline = deadline.trim() !== "" && !DATE_RE.test(deadline.trim());

  async function save() {
    if (!title.trim() || badDeadline) return;
    const patch: Record<string, unknown> = {};
    if (title !== campaign.title) patch.title = title.trim();
    if (description !== (campaign.description ?? "")) {
      // Explicit null clears the column, which is how a form empties a value.
      patch.description = description.trim() || null;
    }
    if (!locked) {
      const amount = budget ? Number(budget) : null;
      if (amount !== campaign.budget_amount) patch.budget_amount = amount;
      // A currency without an amount is not a budget: the two travel
      // together or both go null, exactly as the create form posts them.
      const cur = amount === null ? null : currency;
      if (cur !== campaign.budget_currency) patch.budget_currency = cur;
      const due = deadline.trim() || null;
      if (due !== campaign.deadline) patch.deadline = due;
      if (JSON.stringify(deliverables) !== JSON.stringify(campaign.deliverables)) {
        patch.deliverables = deliverables;
      }
    }
    /* OUTSIDE the lock, on purpose. An explicit [] on a targeting list is how
       a brand clears that dimension, so an emptied picker is sent rather than
       silently skipped. */
    const target = targetingBody(targeting);
    if (target.is_open !== campaign.is_open) patch.is_open = target.is_open;
    if (JSON.stringify(target.target_categories) !== JSON.stringify(campaign.target_categories)) {
      patch.target_categories = target.target_categories;
    }
    if (JSON.stringify(target.target_countries) !== JSON.stringify(campaign.target_countries)) {
      patch.target_countries = target.target_countries;
    }
    if (target.target_min_followers !== campaign.target_min_followers) {
      patch.target_min_followers = target.target_min_followers;
    }
    if (target.target_max_followers !== campaign.target_max_followers) {
      patch.target_max_followers = target.target_max_followers;
    }
    if (Object.keys(patch).length === 0) {
      // Nothing to say: closing beats posting an empty PATCH just to hear
      // the campaign read back unchanged.
      onClose();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaign.id}`, { method: "PATCH", token, body: patch });
      onSaved();
    } catch (e) {
      setError(errorText(e, t));
      setBusy(false);
    }
  }

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{t("campaign.editTitle")}</Text>
      {error ? <Banner kind="error">{error}</Banner> : null}

      <Field label={t("campaign.name")} value={title} onChangeText={setTitle} />
      <Field
        label={t("campaign.description")}
        value={description}
        onChangeText={setDescription}
        multiline
        numberOfLines={4}
        maxLength={MAX_DESCRIPTION_LENGTH}
        placeholder={t("campaign.descriptionPlaceholder")}
      />

      {locked ? <Hint>{t("campaign.editLocked")}</Hint> : null}

      {locked ? (
        <View style={{ marginVertical: space(2) }}>
          <Text style={styles.lockedLine}>
            {t("campaign.budget")}:{" "}
            {campaign.budget_amount
              ? `${campaign.budget_amount} ${campaign.budget_currency}`
              : t("campaign.noBudget")}
          </Text>
          <Text style={styles.lockedLine}>
            {t("campaign.deadline")}: {campaign.deadline || "—"}
          </Text>
          <Text style={[styles.fieldLabel, { marginTop: space(2) }]}>{t("campaign.deliverables")}</Text>
          <DeliverableRows value={deliverables} onChange={setDeliverables} disabled />
        </View>
      ) : (
        <>
          <View style={{ flexDirection: "row", gap: space(3) }}>
            <View style={{ flex: 2 }}>
              <Field
                label={t("campaign.budget")}
                value={budget}
                onChangeText={(v) => setBudget(v.replace(/\D/g, ""))}
                keyboardType="number-pad"
                placeholder="500000"
              />
            </View>
            <View style={{ flex: 3 }}>
              <Text style={styles.fieldLabel}>{t("campaign.currency")}</Text>
              <ChoiceGroup
                options={CURRENCIES.map((c) => ({ value: c, label: c }))}
                value={currency}
                onChange={setCurrency}
              />
            </View>
          </View>
          <Field
            label={t("campaign.deadline")}
            value={deadline}
            onChangeText={setDeadline}
            placeholder="2026-12-31"
            autoCapitalize="none"
            hint={t("campaign.deadlineHint")}
          />
          {badDeadline ? <Banner kind="error">{t("campaign.deadlineBad")}</Banner> : null}
          <Text style={styles.fieldLabel}>{t("campaign.deliverables")}</Text>
          <DeliverableRows value={deliverables} onChange={setDeliverables} />
          <View style={{ height: space(3) }} />
        </>
      )}

      {/* Never disabled, whatever `locked` says: targeting is not a term. */}
      <TargetingFields value={targeting} onChange={setTargeting} />

      <View style={{ height: space(3) }} />
      <PrimaryButton
        title={busy ? t("common.working") : t("campaign.saveEdit")}
        onPress={save}
        loading={busy}
        disabled={!title.trim() || badDeadline}
      />
      <View style={{ height: space(2) }} />
      <GhostButton title={t("campaign.cancelEdit")} onPress={onClose} disabled={busy} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 12,
    padding: space(4),
    marginTop: space(3),
  },
  title: { fontSize: font.h2, fontFamily: family.display, color: colors.ink, marginBottom: space(3) },
  fieldLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) },
  lockedLine: { fontFamily: family.body, fontSize: font.small, color: colors.ink, marginTop: 2 },
});
