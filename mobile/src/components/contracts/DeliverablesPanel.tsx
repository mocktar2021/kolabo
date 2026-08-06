import { useCallback, useEffect, useState } from "react";
import { Linking, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import {
  REVIEW_WINDOW_DAYS,
  openSubmission,
  type DeliverableSubmission,
} from "../../lib/contractTypes";
import { Banner, Field, GhostButton, Hint, PrimaryButton, SectionTitle } from "../ui";
import { colors, font, radius, space } from "../../theme";

/* The work, on the contract it was agreed in — the mobile twin of web's
   DeliverablesPanel. Approving a submission RELEASES the escrow (the D2 rule),
   so approve is one tap with the consequence stated next to it, and request-
   changes needs a reason. There is no standalone release button anywhere: on
   both clients, confirming delivery IS approving the open submission. */
export function DeliverablesPanel({
  contractId,
  isBusiness,
  hasEscrow,
  escrowHeld,
  onChanged,
}: {
  contractId: string;
  isBusiness: boolean;
  hasEscrow: boolean;
  escrowHeld: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<DeliverableSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [link, setLink] = useState("");
  const [note, setNote] = useState("");
  const [asking, setAsking] = useState(false);
  const [reviewNote, setReviewNote] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await api<DeliverableSubmission[]>(`/deliverables?contract_id=${contractId}`));
      setError(null);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setLoading(false);
    }
  }, [contractId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  /* Every write refreshes this panel and tells the parent, because approving
     moved the escrow and the money card above is now describing money that
     just left. */
  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
      await onChanged();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  const open = openSubmission(rows);
  const canSubmit = !isBusiness && escrowHeld && !open;
  const canReview = isBusiness && escrowHeld && !!open;
  const nothingToSend = !link.trim();

  return (
    <View>
      <SectionTitle>{t("deliv.title")}</SectionTitle>
      <Hint>{t("deliv.sub")}</Hint>
      {error ? <Banner kind="error">{error}</Banner> : null}

      {!hasEscrow ? (
        <Hint>{t("deliv.notFunded")}</Hint>
      ) : loading ? null : (
        <>
          {rows.length === 0 ? (
            <Hint>{isBusiness ? t("deliv.emptyBrand") : t("deliv.emptyCreator")}</Hint>
          ) : null}
          {rows.length === 0 && isBusiness ? <Hint>{t("deliv.emptyBrandHint")}</Hint> : null}

          {/* The brand's answer, only on an attempt awaiting one. */}
          {canReview && open ? (
            <View style={{ marginTop: space(3) }}>
              <Text style={styles.h4}>{t("deliv.reviewTitle")}</Text>
              <Hint>{t("deliv.awaitingReview")}</Hint>
              {!asking ? (
                <>
                  <Hint>{t("deliv.approveWarning")}</Hint>
                  <View style={{ height: space(2) }} />
                  <PrimaryButton
                    title={busy ? "…" : t("deliv.approve")}
                    onPress={() => act(() => api(`/deliverables/${open.id}/approve`, { method: "POST" }))}
                    loading={busy}
                  />
                  <View style={{ height: space(2) }} />
                  <GhostButton title={t("deliv.requestChanges")} onPress={() => { setAsking(true); setReviewNote(""); }} />
                </>
              ) : (
                <>
                  <Field
                    label={t("deliv.reviewNoteLabel")}
                    value={reviewNote}
                    onChangeText={setReviewNote}
                    multiline
                    numberOfLines={3}
                    placeholder={t("deliv.reviewNotePlaceholder")}
                  />
                  <Hint>{t("deliv.changesKeepEscrow")}</Hint>
                  <View style={{ height: space(2) }} />
                  <PrimaryButton
                    title={busy ? "…" : t("deliv.sendRequest")}
                    onPress={() =>
                      act(async () => {
                        await api(`/deliverables/${open.id}/request-changes`, {
                          method: "POST",
                          body: { note: reviewNote.trim() },
                        });
                        setAsking(false);
                        setReviewNote("");
                      })
                    }
                    loading={busy}
                    disabled={!reviewNote.trim()}
                  />
                  <View style={{ height: space(2) }} />
                  <GhostButton title={t("common.cancel")} onPress={() => setAsking(false)} />
                </>
              )}
            </View>
          ) : null}

          {/* The creator's side: with the brand, or a withdraw. */}
          {!isBusiness && open ? (
            <View style={{ marginTop: space(3) }}>
              <Banner kind="info">{t("deliv.awaitingReviewCreator")}</Banner>
              <Hint>{t("deliv.withdrawHint")}</Hint>
              <View style={{ height: space(2) }} />
              <GhostButton
                title={t("deliv.withdraw")}
                onPress={() => act(() => api(`/deliverables/${open.id}/withdraw`, { method: "POST" }))}
                disabled={busy}
              />
            </View>
          ) : null}

          {canSubmit ? (
            <View style={{ marginTop: space(3) }}>
              <Text style={styles.h4}>{t("deliv.submitTitle")}</Text>
              <Field
                label={t("deliv.linkLabel")}
                value={link}
                onChangeText={setLink}
                autoCapitalize="none"
                keyboardType="url"
                placeholder={t("deliv.linkPlaceholder")}
              />
              <Field
                label={t("deliv.noteLabel")}
                value={note}
                onChangeText={setNote}
                multiline
                numberOfLines={3}
              />
              {nothingToSend ? <Hint>{t("deliv.needSomething")}</Hint> : null}
              <Hint>{t("deliv.submitHint", { n: REVIEW_WINDOW_DAYS })}</Hint>
              <View style={{ height: space(2) }} />
              <PrimaryButton
                title={busy ? "…" : t("deliv.submit")}
                onPress={() =>
                  act(async () => {
                    await api("/deliverables", {
                      method: "POST",
                      body: {
                        contract_id: contractId,
                        link_url: link.trim() || null,
                        note: note.trim() || null,
                        media_ids: [],
                      },
                    });
                    setLink("");
                    setNote("");
                  })
                }
                loading={busy}
                disabled={nothingToSend}
              />
            </View>
          ) : null}

          {rows.length > 0 ? (
            <View style={{ marginTop: space(4) }}>
              <Text style={styles.h4}>{t("deliv.history")}</Text>
              {rows.map((r) => (
                <View key={r.id} style={styles.histRow}>
                  <Text style={[styles.statusChip, chipStyle(r.status)]}>{t(`deliv.status_${r.status}`)}</Text>
                  {r.link_url ? (
                    <Text style={styles.link} onPress={() => Linking.openURL(r.link_url as string)}>
                      {t("deliv.viewPost")}
                    </Text>
                  ) : null}
                  {r.note ? <Text style={styles.note}>{r.note}</Text> : null}
                  {r.review_note ? (
                    <Text style={styles.reviewNote}>
                      <Text style={{ fontWeight: "700" }}>{t("deliv.reviewNoteShown")}</Text> {r.review_note}
                    </Text>
                  ) : null}
                </View>
              ))}
            </View>
          ) : null}
        </>
      )}
    </View>
  );
}

function chipStyle(status: string) {
  if (status === "approved") return { backgroundColor: "#e7f6f0", color: colors.success };
  if (status === "changes_requested") return { backgroundColor: "#fdecec", color: colors.danger };
  return { backgroundColor: colors.surface2, color: colors.muted };
}

const styles = StyleSheet.create({
  h4: { fontSize: font.body, fontWeight: "700", color: colors.ink, marginBottom: space(1) },
  histRow: { borderTopWidth: 1, borderTopColor: colors.line, paddingVertical: space(3) },
  statusChip: {
    alignSelf: "flex-start",
    fontSize: font.tiny,
    fontWeight: "600",
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
  },
  link: { color: colors.teal600, fontWeight: "600", fontSize: font.small, marginTop: space(2) },
  note: { color: colors.ink, fontSize: font.small, marginTop: space(2) },
  reviewNote: { color: colors.muted, fontSize: font.small, marginTop: space(2) },
});
