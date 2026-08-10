import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { SELLABLE_PLATFORMS, deliverableLabel, deliverablesFor } from "../../lib/platforms";
import type { Deliverable } from "../../lib/campaignTypes";
import { ChoiceGroup, GhostButton } from "../ui";
import { colors, family, font, radius, space } from "../../theme";

/* The most a single deliverable row goes to. Far past any real brief, and a
   cap the stepper enforces so a hold on the + never runs away. The backend
   only asks for >= 1; this ceiling is the form being kind, not a contract. */
const MAX_QTY = 20;

/* A fresh row starts on the first platform's first deliverable so the pair is
   valid by construction; the backend validates every pair against the same
   catalog and answers 400 for anything else. */
export function emptyDeliverable(): Deliverable {
  const platform = SELLABLE_PLATFORMS[0].id;
  return { platform, type: deliverablesFor(platform)[0], quantity: 1 };
}

/* The deliverable rows of a brief. A controlled list the parent owns: the
   create form posts it whole. Switching platform resets the type to that
   platform's first deliverable — keeping the old type would silently build an
   invalid pair (a TikTok "reel") that only surfaces as a 400 on submit.

   Quantity is a stepper, not a text box: a fat finger on a number field turns
   "10 reels" into "100 reels" and the brand only finds out when the proposals
   come back absurd. The web app uses a bounded dropdown for the same reason;
   a stepper is the one-thumb equivalent. */
export function DeliverableRows({
  value,
  onChange,
  disabled = false,
}: {
  value: Deliverable[];
  onChange: (next: Deliverable[]) => void;
  /* The locked case, not a loading case: a published campaign somebody has
     priced against keeps its deliverables read-only, and the add button goes
     away with them — a row that cannot be edited is not a row anybody should
     be able to add next to. */
  disabled?: boolean;
}) {
  const { t } = useTranslation();

  function update(i: number, patch: Partial<Deliverable>) {
    onChange(value.map((d, idx) => (idx === i ? { ...d, ...patch } : d)));
  }

  function changePlatform(i: number, platform: string) {
    update(i, { platform, type: deliverablesFor(platform)[0] });
  }

  function setQty(i: number, qty: number) {
    update(i, { quantity: Math.min(MAX_QTY, Math.max(1, qty)) });
  }

  /* Locked: the rows as a plain read, no editors and no add button. Static
     text rather than greyed-out controls because a chip row has no native
     disabled look and a dead-looking picker still invites taps. */
  if (disabled) {
    return (
      <View style={{ gap: space(1) }}>
        {value.map((d, i) => (
          <Text key={i} style={styles.lockedRow}>
            {d.quantity} × {deliverableLabel(d.type)} —{" "}
            {SELLABLE_PLATFORMS.find((p) => p.id === d.platform)?.label ?? d.platform}
          </Text>
        ))}
      </View>
    );
  }

  return (
    <View>
      {value.map((d, i) => (
        <View key={i} style={styles.row}>
          <View style={styles.rowHead}>
            <Text style={styles.rowLabel}>
              {t("campaign.deliverableN", { n: i + 1 })}
            </Text>
            <Text
              style={[styles.remove, value.length === 1 && styles.removeOff]}
              onPress={value.length === 1 ? undefined : () => onChange(value.filter((_, idx) => idx !== i))}
            >
              {t("campaign.removeDeliverable")}
            </Text>
          </View>

          <Text style={styles.fieldLabel}>{t("campaign.platform")}</Text>
          <ChoiceGroup
            options={SELLABLE_PLATFORMS.map((p) => ({ value: p.id, label: p.label }))}
            value={d.platform}
            onChange={(v) => changePlatform(i, v)}
          />

          <View style={{ height: space(3) }} />
          <Text style={styles.fieldLabel}>{t("campaign.deliverableType")}</Text>
          <ChoiceGroup
            options={deliverablesFor(d.platform).map((ty) => ({ value: ty, label: deliverableLabel(ty) }))}
            value={d.type}
            onChange={(v) => update(i, { type: v })}
          />

          <View style={{ height: space(3) }} />
          <Text style={styles.fieldLabel}>{t("campaign.quantity")}</Text>
          <View style={styles.stepper}>
            <Pressable
              onPress={() => setQty(i, d.quantity - 1)}
              disabled={d.quantity <= 1}
              style={({ pressed }) => [
                styles.stepBtn,
                d.quantity <= 1 && styles.stepOff,
                pressed && d.quantity > 1 && styles.stepPressed,
              ]}
              accessibilityLabel={t("campaign.qtyLess")}
            >
              <Text style={styles.stepGlyph}>−</Text>
            </Pressable>
            <Text style={styles.qty}>{d.quantity}</Text>
            <Pressable
              onPress={() => setQty(i, d.quantity + 1)}
              disabled={d.quantity >= MAX_QTY}
              style={({ pressed }) => [
                styles.stepBtn,
                d.quantity >= MAX_QTY && styles.stepOff,
                pressed && d.quantity < MAX_QTY && styles.stepPressed,
              ]}
              accessibilityLabel={t("campaign.qtyMore")}
            >
              <Text style={styles.stepGlyph}>+</Text>
            </Pressable>
          </View>
        </View>
      ))}

      <GhostButton title={t("campaign.addDeliverable")} onPress={() => onChange([...value, emptyDeliverable()])} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
    marginBottom: space(3),
  },
  rowHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: space(2),
  },
  rowLabel: { fontSize: font.small, fontFamily: family.bodyBold, color: colors.ink },
  remove: { fontSize: font.small, color: colors.danger, fontFamily: family.bodySemi },
  removeOff: { color: colors.muted, opacity: 0.5 },
  fieldLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) },
  stepper: { flexDirection: "row", alignItems: "center", gap: space(3) },
  stepBtn: {
    width: 44,
    height: 44,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
  },
  stepPressed: { backgroundColor: colors.surface },
  stepOff: { opacity: 0.4 },
  stepGlyph: { fontSize: 22, fontFamily: family.display, color: colors.ink, lineHeight: 24 },
  qty: { fontSize: font.h2, fontFamily: family.display, color: colors.ink, minWidth: 32, textAlign: "center" },
  lockedRow: { fontFamily: family.body, fontSize: font.small, color: colors.ink },
});
