import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { deliverableLabel, PLATFORM_LABELS } from "../lib/platforms";
import type { OpenBrief } from "../lib/boardTypes";
import { ApplyForm } from "../components/board/ApplyForm";
import { Banner, GhostButton, Hint, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
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

export default function BoardScreen({ navigation }: AppScreenProps<"Board">) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [briefs, setBriefs] = useState<OpenBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      // Rendered in the order they arrive — the ranking is the server's.
      setBriefs(await api<OpenBrief[]>("/campaigns/open", { token }));
      setError(null);
    } catch {
      setError(t("board.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function markApplied(id: string) {
    setBriefs((rows) => rows.map((r) => (r.id === id ? { ...r, has_applied: true } : r)));
  }

  return (
    <Screen>
      <View style={{ marginBottom: space(2) }}>
        <GhostButton title={t("common.back")} onPress={() => navigation.goBack()} />
      </View>
      <Title>{t("board.title")}</Title>
      <Subtitle>{t("board.sub")}</Subtitle>
      <Hint>{t("board.rankHint")}</Hint>

      {error ? <Banner kind="error">{error}</Banner> : null}

      {loading ? null : briefs.length === 0 ? (
        <View style={{ marginTop: space(3) }}>
          <Text style={{ color: colors.ink, fontSize: font.body }}>{t("board.empty")}</Text>
          <Hint>{t("board.emptyHint")}</Hint>
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
