import { useState } from "react";
import { StyleSheet, Switch, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/dates";
import { PLATFORM_LABELS, deliverableLabel } from "../lib/platforms";
import { EMPTY_TARGETING, targetingBody, type Campaign, type Deliverable, type Targeting } from "../lib/campaignTypes";
import { DeliverableRows, emptyDeliverable } from "../components/campaigns/DeliverableRows";
import { TargetingFields } from "../components/campaigns/TargetingFields";
import {
  Banner,
  Card,
  ChoiceGroup,
  Field,
  GhostButton,
  Hint,
  PrimaryButton,
  Screen,
  SectionTitle,
  Subtitle,
} from "../components/ui";
import { colors, family, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

const CURRENCIES = ["XOF", "XAF", "GHS", "NGN"];
const MAX_DESCRIPTION_LENGTH = 5000;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const published = status === "published";
  return (
    <Text style={[styles.chip, published ? styles.chipPublished : styles.chipMuted]}>
      {t(`campaign.status_${status}`, { defaultValue: status })}
    </Text>
  );
}

export default function CampaignNewScreen({ navigation }: AppScreenProps<"CampaignNew">) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("");
  const [currency, setCurrency] = useState("XOF");
  const [deadline, setDeadline] = useState("");
  const [deliverables, setDeliverables] = useState<Deliverable[]>([emptyDeliverable()]);
  const [targeting, setTargeting] = useState<Targeting>(EMPTY_TARGETING);
  const [publishNow, setPublishNow] = useState(false);

  const [created, setCreated] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const badDeadline = deadline.trim() !== "" && !DATE_RE.test(deadline.trim());
  const canSubmit = title.trim() !== "" && deliverables.length > 0 && !badDeadline;

  async function submit() {
    if (!canSubmit) return;
    setError(null);
    setBusy(true);
    try {
      const campaign = await api<Campaign>("/campaigns/", {
        method: "POST",
        token,
        body: {
          title: title.trim(),
          // Null rather than an empty string: the column is nullable and "no
          // description" is an absence, not a description made of nothing.
          description: description.trim() || null,
          budget_amount: budget ? Number(budget) : null,
          budget_currency: budget ? currency : null,
          deliverables,
          deadline: deadline.trim() || null,
          publish: publishNow,
          ...targetingBody(targeting),
        },
      });
      setCreated(campaign);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    if (!created) return;
    setError(null);
    setBusy(true);
    try {
      const updated = await api<Campaign>(`/campaigns/${created.id}/publish`, { method: "POST", token });
      setCreated(updated);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setTitle("");
    setDescription("");
    setBudget("");
    setCurrency("XOF");
    setDeadline("");
    setDeliverables([emptyDeliverable()]);
    setTargeting(EMPTY_TARGETING);
    setPublishNow(false);
    setCreated(null);
    setError(null);
  }

  return (
    <Screen>
      <Subtitle>{t("campaign.sub")}</Subtitle>

      {error ? <Banner kind="error">{error}</Banner> : null}

      {created ? (
        <Card>
          <View style={styles.createdHead}>
            <Text style={styles.createdTitle}>{created.title}</Text>
            <StatusChip status={created.status} />
          </View>
          <Text style={styles.createdMeta}>
            {created.budget_amount
              ? `${created.budget_amount.toLocaleString(i18n.language)} ${created.budget_currency}`
              : t("campaign.noBudget")}
            {created.deadline ? ` · ${formatDate(created.deadline, i18n.language)}` : ""}
          </Text>
          {created.description ? <Text style={styles.createdDesc}>{created.description}</Text> : null}
          <View style={{ gap: space(1), marginBottom: space(3) }}>
            {created.deliverables.map((d, i) => (
              <Text key={i} style={styles.createdDeliv}>
                {d.quantity} × {deliverableLabel(d.type)} · {PLATFORM_LABELS[d.platform] ?? d.platform}
              </Text>
            ))}
          </View>
          {created.is_open ? <Hint>{t("target.openHint")}</Hint> : null}
          <View style={{ height: space(3) }} />
          {created.status !== "published" ? (
            <PrimaryButton
              title={busy ? t("common.working") : t("campaign.publish")}
              onPress={publish}
              loading={busy}
            />
          ) : (
            <Banner kind="success">{t("campaign.published")}</Banner>
          )}
          <View style={{ height: space(2) }} />
          <GhostButton title={t("campaign.another")} onPress={reset} />
          <View style={{ height: space(2) }} />
          <GhostButton title={t("campaign.toList")} onPress={() => navigation.navigate("Campaigns")} />
        </Card>
      ) : (
        <Card>
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

          <SectionTitle>{t("campaign.deliverables")}</SectionTitle>
          <DeliverableRows value={deliverables} onChange={setDeliverables} />

          <SectionTitle>{t("target.legend")}</SectionTitle>
          <TargetingFields value={targeting} onChange={setTargeting} />

          <View style={styles.publishRow}>
            <Text style={styles.publishLabel}>{t("campaign.publishNow")}</Text>
            <Switch
              value={publishNow}
              onValueChange={setPublishNow}
              trackColor={{ true: colors.teal, false: colors.line }}
              thumbColor={colors.white}
            />
          </View>

          <PrimaryButton
            title={busy ? t("common.working") : t("campaign.create")}
            onPress={submit}
            loading={busy}
            disabled={!canSubmit}
          />
        </Card>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  fieldLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) },
  publishRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginVertical: space(4),
  },
  publishLabel: { fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink },
  chip: {
    fontSize: font.tiny,
    fontFamily: family.bodySemi,
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
  },
  chipPublished: { backgroundColor: "#e7f6f0", color: colors.teal600 },
  chipMuted: { backgroundColor: colors.surface2, color: colors.muted },
  createdHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space(2) },
  createdTitle: { fontSize: font.h2, fontFamily: family.display, color: colors.ink, flexShrink: 1 },
  createdMeta: { fontFamily: family.body, fontSize: font.small, color: colors.muted, marginTop: space(2), marginBottom: space(2) },
  createdDesc: { fontFamily: family.body, fontSize: font.small, color: colors.ink, marginBottom: space(3) },
  createdDeliv: { fontFamily: family.body, fontSize: font.small, color: colors.ink },
});
