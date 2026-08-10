import { StyleSheet, Switch, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { CATEGORIES } from "../../lib/categories";
import { COUNTRIES, countryName } from "../../lib/countries";
import type { Targeting } from "../../lib/campaignTypes";
import { Field, Hint, MultiChoiceGroup } from "../ui";
import { colors, family, font, space } from "../../theme";

/* Who a brand is hoping to reach with a brief, as a form.

   THE PRODUCT RULE THIS CONTROL EXISTS TO COMMUNICATE: targeting RANKS, it
   does not EXCLUDE. A creator who matches sees the brief first; any signed-in
   creator may apply to any open brief, and nothing set here removes a row from
   anybody's board. backend/app/modules/campaigns/board.py is the authority.
   The rule is stated on screen (target.explain) and not only in this comment,
   because a brand that believes it set a hard filter will read an off-target
   application as a bug and decline it unread.

   is_open is a separate decision from targeting and sits above it: it is the
   one setting on this form whose consequence arrives from strangers. */
export function TargetingFields({
  value,
  onChange,
}: {
  value: Targeting;
  onChange: (next: Targeting) => void;
}) {
  const { t, i18n } = useTranslation();

  function toggle(key: "categories" | "countries", entry: string) {
    const current = value[key];
    onChange({
      ...value,
      [key]: current.includes(entry) ? current.filter((c) => c !== entry) : [...current, entry],
    });
  }

  return (
    <View>
      <View style={styles.switchRow}>
        <View style={{ flexShrink: 1, paddingRight: space(3) }}>
          <Text style={styles.switchLabel}>{t("target.open")}</Text>
          <Text style={styles.switchHint}>{t("target.openHint")}</Text>
        </View>
        <Switch
          value={value.is_open}
          onValueChange={(v) => onChange({ ...value, is_open: v })}
          trackColor={{ true: colors.teal, false: colors.line }}
          thumbColor={colors.white}
        />
      </View>

      <Text style={styles.legend}>{t("target.legend")}</Text>
      <Hint>{t("target.explain")}</Hint>

      <Text style={styles.groupLabel}>{t("target.categories")}</Text>
      <MultiChoiceGroup
        options={CATEGORIES.map((c) => ({ value: c, label: t(`cat.${c}`) }))}
        values={value.categories}
        onToggle={(c) => toggle("categories", c)}
      />

      <Text style={styles.groupLabel}>{t("target.countries")}</Text>
      <MultiChoiceGroup
        options={COUNTRIES.map((c) => ({ value: c.code, label: countryName(c, i18n.language) }))}
        values={value.countries}
        onToggle={(c) => toggle("countries", c)}
      />

      <View style={{ height: space(3) }} />
      <View style={{ flexDirection: "row", gap: space(3) }}>
        <View style={{ flex: 1 }}>
          <Field
            label={t("target.minFollowers")}
            value={value.minFollowers}
            onChangeText={(v) => onChange({ ...value, minFollowers: v.replace(/\D/g, "") })}
            keyboardType="number-pad"
            placeholder="5000"
          />
        </View>
        <View style={{ flex: 1 }}>
          <Field
            label={t("target.maxFollowers")}
            value={value.maxFollowers}
            onChangeText={(v) => onChange({ ...value, maxFollowers: v.replace(/\D/g, "") })}
            keyboardType="number-pad"
            placeholder="100000"
          />
        </View>
      </View>
      <Hint>{t("target.followersHint")}</Hint>
    </View>
  );
}

const styles = StyleSheet.create({
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: space(4),
  },
  switchLabel: { fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink },
  switchHint: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: space(1) },
  legend: { fontSize: font.small, fontFamily: family.bodyBold, color: colors.ink, marginBottom: space(1.5) },
  groupLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginTop: space(3), marginBottom: space(1.5) },
});
