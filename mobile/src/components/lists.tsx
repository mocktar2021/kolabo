import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { colors, family, font, radius, space } from "../theme";

/* The two list controls the campaign, contract and invitation lists share,
   mirrored from web/src/components/ListFilter.tsx and ListTabs.tsx. They
   answer different questions: a TAB is the lifecycle question — is this still
   my problem, or is it history — asked first every time, so it sits above.
   The CHIPS are the detail question inside whichever answer was picked.

   Both work on lists the screen already holds in memory: each of these lists
   fetches its whole set in one request and is short at pilot volume, so
   narrowing is a filter of an array already on screen. When a list outgrows
   that, the fix is a query param on its endpoint, not a rewrite here. */

export type FilterOption = { value: string; label: string };

/* Chips. "" is All, always the first chip and always in reach — clearing is
   done by choosing All, never by re-tapping the active chip. Renders nothing
   with fewer than two real options: a single-status list is a set of chips
   whose only outcome is the page somebody is already looking at. Derive
   options from the values actually present so no chip matches zero rows. */
export function ListFilter({
  options,
  value,
  onChange,
}: {
  options: FilterOption[];
  value: string;
  onChange: (next: string) => void;
}) {
  const { t } = useTranslation();
  if (options.length < 2) return null;

  const chips: FilterOption[] = [{ value: "", label: t("lf.all") }, ...options];
  return (
    <View style={styles.chipRow}>
      {chips.map((chip) => {
        const active = chip.value === value;
        return (
          <Pressable key={chip.value || "__all"} onPress={() => onChange(chip.value)}>
            <Text style={[styles.chip, active && styles.chipActive]}>{chip.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export type Tab = "active" | "completed";

/* Active / Completed with counts. The counts are the point, not decoration:
   "Completed 12" is what tells a reader the shelf exists and is worth
   opening, and a zero count is still shown because it teaches the split
   before there is anything on the other side. Always rendered (the caller
   gates on the list being non-empty), unlike ListFilter — hiding it would
   leave a reader looking for finished work in the wrong place the first time
   something completed. */
export function ListTabs({
  active,
  activeCount,
  completedCount,
  onChange,
}: {
  active: Tab;
  activeCount: number;
  completedCount: number;
  onChange: (next: Tab) => void;
}) {
  const { t } = useTranslation();
  const tabs: { value: Tab; label: string; count: number }[] = [
    { value: "active", label: t("lf.tabActive"), count: activeCount },
    { value: "completed", label: t("lf.tabCompleted"), count: completedCount },
  ];
  return (
    <View style={styles.tabRow}>
      {tabs.map((tab) => {
        const selected = tab.value === active;
        return (
          <Pressable key={tab.value} onPress={() => onChange(tab.value)} style={[styles.tab, selected && styles.tabSelected]}>
            <Text style={[styles.tabText, selected && styles.tabTextSelected]}>
              {tab.label} {tab.count}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: space(2), marginTop: space(3) },
  chip: {
    fontSize: font.tiny,
    fontFamily: family.bodySemi,
    color: colors.muted,
    backgroundColor: colors.surface2,
    borderRadius: radius.pill,
    paddingHorizontal: space(3),
    paddingVertical: space(1.5),
    overflow: "hidden",
  },
  chipActive: { color: colors.white, backgroundColor: colors.teal600, fontFamily: family.bodyBold },
  tabRow: {
    flexDirection: "row",
    gap: space(4),
    marginTop: space(3),
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  tab: { paddingBottom: space(2), borderBottomWidth: 2, borderBottomColor: "transparent" },
  tabSelected: { borderBottomColor: colors.teal600 },
  tabText: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.muted },
  tabTextSelected: { color: colors.teal600, fontFamily: family.bodyBold },
});
