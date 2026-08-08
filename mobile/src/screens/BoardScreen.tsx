import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CATEGORIES } from "../lib/categories";
import { COUNTRIES } from "../lib/countries";
import { SELLABLE_PLATFORMS, deliverableLabel, PLATFORM_LABELS } from "../lib/platforms";
import type { OpenBrief } from "../lib/boardTypes";
import { ApplyForm } from "../components/board/ApplyForm";
import { Banner, ChoiceGroup, Field, GhostButton, Hint, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import { colors, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

function MatchChip({ score }: { score: number }) {
  const { t } = useTranslation();
  const strong = score > 0;
  return (
    <Text style={[styles.match, strong ? styles.matchStrong : styles.matchNone]}>
      {strong ? t("board.matchStrong") : t("board.matchNone")}
    </Text>
  );
}

function BriefCard({ brief, onApplied }: { brief: OpenBrief; onApplied: (id: string) => void }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState(false);
  const blocked = brief.has_applied || sent || brief.is_invited;

  return (
    <View style={styles.card}>
      <View style={styles.top}>
        <View style={{ flexShrink: 1 }}>
          <Text style={styles.brand}>{brief.business_company_name || t("board.unknownBrand")}</Text>
          <Text style={styles.title}>{brief.title}</Text>
        </View>
        <MatchChip score={brief.match_score} />
      </View>

      <Text style={styles.meta}>
        {brief.budget_amount
          ? `${brief.budget_amount.toLocaleString(i18n.language)} ${brief.budget_currency ?? ""}`
          : t("board.noBudget")}
        {" · "}
        {brief.deadline ? `${t("board.deadline")} ${brief.deadline}` : t("board.noDeadline")}
      </Text>

      {brief.description ? <Text style={styles.desc}>{brief.description}</Text> : null}

      <Text style={styles.deliv}>
        <Text style={{ fontWeight: "700", color: colors.muted }}>{t("board.deliverables")}: </Text>
        {brief.deliverables.length === 0
          ? t("board.noDeliverables")
          : brief.deliverables
              .map((d) => `${d.quantity} × ${deliverableLabel(d.type)} (${PLATFORM_LABELS[d.platform] ?? d.platform})`)
              .join(", ")}
      </Text>

      {sent ? <Banner kind="success">{t("board.applySent")}</Banner> : null}

      {brief.is_invited ? (
        <View style={{ marginTop: space(2) }}>
          <Text style={[styles.stateChip, { color: colors.indigo }]}>{t("board.invited")}</Text>
          <Hint>{t("board.invitedHint")}</Hint>
        </View>
      ) : brief.has_applied || sent ? (
        <View style={{ marginTop: space(2) }}>
          <Text style={[styles.stateChip, { color: colors.muted }]}>{t("board.applied")}</Text>
          <Hint>{t("board.appliedHint")}</Hint>
        </View>
      ) : (
        <View style={{ marginTop: space(2) }}>
          {open ? (
            <GhostButton title={t("board.applyCancel")} onPress={() => setOpen(false)} />
          ) : (
            <PrimaryButton title={t("board.apply")} onPress={() => setOpen(true)} />
          )}
          {open ? (
            <ApplyForm
              brief={brief}
              onApplied={() => {
                setSent(true);
                setOpen(false);
                onApplied(brief.id);
              }}
            />
          ) : null}
        </View>
      )}
    </View>
  );
}

/* The creator's filters. Not to be confused with the brand's targeting: one
   NARROWS the list, the other decides its ORDER. Sent as query params so the
   server does the narrowing — the board endpoint takes them natively — and
   only what was actually set is sent: min_budget= empty is a different
   request than no min_budget at all. */
type Filters = {
  minBudget: string;
  maxBudget: string;
  category: string;
  country: string;
  platform: string;
  deadlineBefore: string;
};

const EMPTY_FILTERS: Filters = {
  minBudget: "",
  maxBudget: "",
  category: "",
  country: "",
  platform: "",
  deadlineBefore: "",
};

function filterQuery(f: Filters): string {
  const params = new URLSearchParams();
  if (f.minBudget) params.set("min_budget", f.minBudget);
  if (f.maxBudget) params.set("max_budget", f.maxBudget);
  if (f.category) params.set("category", f.category);
  if (f.country) params.set("country", f.country);
  if (f.platform) params.set("platform", f.platform);
  if (f.deadlineBefore) params.set("deadline_before", f.deadlineBefore);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

function anyFilter(f: Filters): boolean {
  return Object.values(f).some((v) => v !== "");
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export default function BoardScreen({ navigation }: AppScreenProps<"Board">) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [briefs, setBriefs] = useState<OpenBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  /* Draft vs applied, exactly as web: typing never fires a request; the
     Filter button applies the draft, and `applied` is what load() reads. */
  const [draft, setDraft] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);

  const badDeadline = draft.deadlineBefore !== "" && !DATE_RE.test(draft.deadlineBefore);

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      // Rendered in the order they arrive — the ranking is the server's.
      setBriefs(await api<OpenBrief[]>(`/campaigns/open${filterQuery(applied)}`, { token }));
      setError(null);
    } catch {
      setError(t("board.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [token, t, applied]);

  useEffect(() => {
    void load();
  }, [load]);

  function reset() {
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
  }

  const filtered = anyFilter(applied);

  function markApplied(id: string) {
    setBriefs((rows) => rows.map((r) => (r.id === id ? { ...r, has_applied: true } : r)));
  }

  return (
    <Screen
      loading={loading}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
      <Title>{t("board.title")}</Title>
      <Subtitle>{t("board.sub")}</Subtitle>
      <Hint>{t("board.rankHint")}</Hint>

      <View style={{ marginTop: space(2), marginBottom: space(2) }}>
        <GhostButton
          title={showFilters ? t("board.hideFilters") : t("board.filters")}
          onPress={() => setShowFilters((v) => !v)}
        />
      </View>

      {showFilters ? (
        <View style={styles.filters}>
          <View style={{ flexDirection: "row", gap: space(2) }}>
            <View style={{ flex: 1 }}>
              <Field
                label={t("board.budgetMin")}
                value={draft.minBudget}
                onChangeText={(v) => setDraft({ ...draft, minBudget: v.replace(/\D/g, "") })}
                keyboardType="number-pad"
                placeholder="50000"
              />
            </View>
            <View style={{ flex: 1 }}>
              <Field
                label={t("board.budgetMax")}
                value={draft.maxBudget}
                onChangeText={(v) => setDraft({ ...draft, maxBudget: v.replace(/\D/g, "") })}
                keyboardType="number-pad"
                placeholder="500000"
              />
            </View>
          </View>

          <Text style={styles.filterLabel}>{t("board.niche")}</Text>
          <ChoiceGroup
            options={[
              { value: "", label: t("board.nicheAll") },
              ...CATEGORIES.map((c) => ({ value: c, label: t(`cat.${c}`) })),
            ]}
            value={draft.category}
            onChange={(v) => setDraft({ ...draft, category: v })}
          />

          <Text style={styles.filterLabel}>{t("board.country")}</Text>
          <ChoiceGroup
            options={[
              { value: "", label: t("board.countryAll") },
              ...COUNTRIES.map((c) => ({ value: c.code, label: c.name })),
            ]}
            value={draft.country}
            onChange={(v) => setDraft({ ...draft, country: v })}
          />

          <Text style={styles.filterLabel}>{t("board.platform")}</Text>
          <ChoiceGroup
            options={[
              { value: "", label: t("board.platformAll") },
              ...SELLABLE_PLATFORMS.map((p) => ({ value: p.id, label: p.label })),
            ]}
            value={draft.platform}
            onChange={(v) => setDraft({ ...draft, platform: v })}
          />

          <View style={{ marginTop: space(3) }}>
            <Field
              label={t("board.deadlineBefore")}
              value={draft.deadlineBefore}
              onChangeText={(v) => setDraft({ ...draft, deadlineBefore: v })}
              placeholder="2026-12-31"
              autoCapitalize="none"
            />
          </View>
          {badDeadline ? <Banner kind="error">{t("board.deadlineBad")}</Banner> : null}

          <PrimaryButton
            title={t("board.applyFilters")}
            onPress={() => setApplied(draft)}
            disabled={badDeadline}
          />
          {filtered || anyFilter(draft) ? (
            <View style={{ marginTop: space(2) }}>
              <GhostButton title={t("board.resetFilters")} onPress={reset} />
            </View>
          ) : null}
          <Hint>{t("board.filterNote")}</Hint>
        </View>
      ) : null}

      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}

      {loading ? null : briefs.length === 0 ? (
        <View style={{ marginTop: space(3) }}>
          <Text style={{ color: colors.ink, fontSize: font.body }}>
            {filtered ? t("board.emptyFiltered") : t("board.empty")}
          </Text>
          <Hint>{filtered ? t("board.emptyFilteredHint") : t("board.emptyHint")}</Hint>
        </View>
      ) : (
        <View style={{ gap: space(3), marginTop: space(2) }}>
          {briefs.map((brief) => (
            <BriefCard key={brief.id} brief={brief} onApplied={markApplied} />
          ))}
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  filters: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
    marginBottom: space(3),
  },
  filterLabel: { fontSize: font.small, fontWeight: "600", color: colors.ink, marginTop: space(3), marginBottom: space(1.5) },
  card: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(4),
  },
  top: { flexDirection: "row", justifyContent: "space-between", gap: space(2) },
  brand: { fontSize: font.tiny, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  title: { fontSize: font.body, fontWeight: "700", color: colors.ink, marginTop: 2 },
  match: {
    fontSize: font.tiny,
    fontWeight: "600",
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
    alignSelf: "flex-start",
  },
  matchStrong: { color: colors.teal600, backgroundColor: "#e7f6f0" },
  matchNone: { color: colors.muted, backgroundColor: colors.surface2 },
  meta: { fontSize: font.small, color: colors.muted, marginTop: space(2) },
  desc: { fontSize: font.small, color: colors.ink, marginTop: space(2), lineHeight: 20 },
  deliv: { fontSize: font.small, color: colors.ink, marginTop: space(2) },
  stateChip: {
    fontSize: font.tiny,
    fontWeight: "600",
    backgroundColor: colors.surface2,
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
    alignSelf: "flex-start",
  },
});
