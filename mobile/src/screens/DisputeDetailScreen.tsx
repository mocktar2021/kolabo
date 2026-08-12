import { useCallback, useEffect, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, mediaSrc, type MediaOut } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { parseApiDate } from "../lib/dates";
import { isDisputeOpen, respondTimeLeft, type DisputeCase } from "../lib/disputeTypes";
import { EvidencePicker } from "../components/disputes/EvidencePicker";
import { Banner, Card, Field, GhostButton, Hint, PrimaryButton, Screen, SectionTitle, Subtitle, Title } from "../components/ui";
import { colors, family, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

function when(iso: string, locale: string): string {
  const d = parseApiDate(iso);
  return d ? d.toLocaleString(locale) : "";
}

function Evidence({ urls }: { urls: string[] }) {
  if (urls.length === 0) return null;
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space(2), marginTop: space(2) }}>
      {urls.map((url) => (
        <Image key={url} source={{ uri: mediaSrc(url) }} style={styles.evidence} />
      ))}
    </View>
  );
}

function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const tone =
    status === "resolved"
      ? { bg: "#e7f6f0", fg: colors.teal600 }
      : status === "withdrawn"
        ? { bg: colors.surface2, fg: colors.muted }
        : { bg: "#fdecec", fg: colors.danger };
  return (
    <Text style={[styles.chip, { backgroundColor: tone.bg, color: tone.fg }]}>
      {t(`dispute.status_${status}`, { defaultValue: status })}
    </Text>
  );
}

export default function DisputeDetailScreen({ navigation, route }: AppScreenProps<"DisputeDetail">) {
  const { t, i18n } = useTranslation();
  const { token, userId } = useAuth();
  const { id } = route.params;

  const [dispute, setDispute] = useState<DisputeCase | null>(null);
  const [body, setBody] = useState("");
  const [evidence, setEvidence] = useState<MediaOut[]>([]);
  const [confirmWithdraw, setConfirmWithdraw] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    try {
      setDispute(await api<DisputeCase>(`/payments/disputes/${id}`, { token }));
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setLoading(false);
    }
  }, [id, token, t]);

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

  const escrow = dispute?.escrow ?? null;
  const open = dispute ? isDisputeOpen(dispute) : false;
  const isOpener = !!dispute && dispute.opened_by_user_id === userId;
  const author = (authorId: string) => (authorId === userId ? t("dispute.you") : t("dispute.unknownParty"));
  const left = dispute && dispute.status === "awaiting_response" ? respondTimeLeft(dispute.respond_by) : null;

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

      {loading ? null : !dispute ? (
        <Hint>{t("dispute.notFound")}</Hint>
      ) : (
        <>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space(2) }}>
            <Title>{t(`dispute.reason_${dispute.reason}`)}</Title>
            <StatusChip status={dispute.status} />
          </View>
          <Subtitle>
            {t("dispute.unknownParty")}
            {escrow ? ` · ${escrow.amount} ${escrow.currency}` : ""}
          </Subtitle>
          {dispute.status === "awaiting_response" ? (
            <Banner kind="info">
              {left
                ? left.unit === "hours"
                  ? t("dispute.respondInHours", { n: left.n })
                  : t("dispute.respondInMinutes", { n: left.n })
                : t("dispute.respondOverdue")}
            </Banner>
          ) : null}

          <Card>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <SectionTitle>{t("dispute.opening")}</SectionTitle>
              <Text style={styles.time}>{when(dispute.created_at, i18n.language)}</Text>
            </View>
            <Text style={styles.author}>{author(dispute.opened_by_user_id)}</Text>
            <Text style={styles.statement}>{dispute.statement}</Text>
            <Evidence urls={dispute.attachments} />
          </Card>

          {dispute.status === "resolved" && escrow ? (
            <>
              <View style={{ height: space(4) }} />
              <Card>
                <SectionTitle>{t("dispute.outcome")}</SectionTitle>
                <View style={styles.outRow}>
                  <Text style={styles.muted}>{t("dispute.outcomeReleased")}</Text>
                  <Text style={styles.ink}>{`${dispute.released_amount ?? 0} ${escrow.currency}`}</Text>
                </View>
                <View style={styles.outRow}>
                  <Text style={styles.muted}>{t("dispute.outcomeRefunded")}</Text>
                  <Text style={styles.ink}>{`${dispute.refunded_amount ?? 0} ${escrow.currency}`}</Text>
                </View>
                {dispute.resolution ? (
                  <>
                    <Hint>{t("dispute.outcomeNote")}</Hint>
                    <Text style={styles.statement}>{dispute.resolution}</Text>
                  </>
                ) : null}
              </Card>
            </>
          ) : null}

          <View style={{ height: space(4) }} />
          <Card>
            <SectionTitle>{t("dispute.thread")}</SectionTitle>
            {dispute.messages.length === 0 ? (
              <Hint>{t("dispute.noMessages")}</Hint>
            ) : (
              dispute.messages.map((m) => (
                <View key={m.id} style={styles.msg}>
                  <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                    <Text style={styles.author}>{author(m.author_user_id)}</Text>
                    <Text style={styles.time}>{when(m.created_at, i18n.language)}</Text>
                  </View>
                  <Text style={styles.statement}>{m.body}</Text>
                  <Evidence urls={m.attachments} />
                </View>
              ))
            )}

            {open ? (
              <View style={{ marginTop: space(3) }}>
                <Field
                  label={t("dispute.thread")}
                  value={body}
                  onChangeText={setBody}
                  multiline
                  numberOfLines={3}
                  placeholder={t("dispute.composerPlaceholder")}
                />
                {userId ? (
                  <EvidencePicker userId={userId} token={token} value={evidence} onChange={setEvidence} />
                ) : null}
                <PrimaryButton
                  title={busy ? "…" : t("dispute.send")}
                  onPress={() =>
                    act(async () => {
                      await api(`/payments/disputes/${dispute.id}/messages`, {
                        method: "POST",
                        token,
                        body: { body: body.trim(), media_ids: evidence.map((e) => e.id) },
                      });
                      setBody("");
                      setEvidence([]);
                    })
                  }
                  loading={busy}
                  disabled={body.trim().length === 0}
                />
              </View>
            ) : null}
          </Card>

          {open && isOpener ? (
            <>
              <View style={{ height: space(4) }} />
              <Card>
                {!confirmWithdraw ? (
                  <GhostButton title={t("dispute.withdraw")} onPress={() => setConfirmWithdraw(true)} disabled={busy} />
                ) : (
                  <>
                    <Hint>{t("dispute.withdrawExplain")}</Hint>
                    <View style={{ height: space(2) }} />
                    <PrimaryButton
                      title={busy ? "…" : t("dispute.withdrawYes")}
                      onPress={() =>
                        act(async () => {
                          await api(`/payments/disputes/${dispute.id}/withdraw`, { method: "POST", token });
                          setConfirmWithdraw(false);
                        })
                      }
                      loading={busy}
                    />
                    <View style={{ height: space(2) }} />
                    <GhostButton title={t("dispute.withdrawNo")} onPress={() => setConfirmWithdraw(false)} disabled={busy} />
                  </>
                )}
              </Card>
            </>
          ) : null}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  chip: {
    fontSize: font.tiny,
    fontFamily: family.bodySemi,
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
  },
  author: { fontSize: font.small, fontFamily: family.bodyBold, color: colors.ink, marginTop: space(1) },
  statement: { fontFamily: family.body, fontSize: font.small, color: colors.ink, marginTop: space(1), lineHeight: 20 },
  time: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted },
  muted: { fontFamily: family.body, fontSize: font.small, color: colors.muted },
  ink: { fontFamily: family.body, fontSize: font.small, color: colors.ink },
  outRow: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 4 },
  msg: { borderTopWidth: 1, borderTopColor: colors.line, paddingVertical: space(3) },
  evidence: { width: 88, height: 88, borderRadius: 8, backgroundColor: colors.surface2 },
});
