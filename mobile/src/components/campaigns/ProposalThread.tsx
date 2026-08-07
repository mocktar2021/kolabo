import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { useAuth } from "../../lib/auth";
import type { ProposalChain } from "../../lib/campaignTypes";
import { Banner, Field, GhostButton, Hint, PrimaryButton } from "../ui";
import { colors, font, radius, space } from "../../theme";

const NOTE_MAX_LENGTH = 2000;

/* The business answering an offer. The note is required — a reply always says
   something — while the two term fields are optional and only sent when
   filled: the endpoint repeats the previous terms for anything omitted, so an
   empty box means "same terms", which is why the current ones sit in the
   placeholders. */
function ReplyForm({ campaignId, latestId, ratePlaceholder, daysPlaceholder, onSent }: {
  campaignId: string;
  latestId: string;
  ratePlaceholder: string;
  daysPlaceholder: string;
  onSent: () => void;
}) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [note, setNote] = useState("");
  const [rate, setRate] = useState("");
  const [days, setDays] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const trimmed = note.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${campaignId}/proposals/${latestId}/reply`, {
        method: "POST",
        token,
        body: {
          note: trimmed,
          ...(rate ? { rate_amount: Number(rate) } : {}),
          ...(days ? { timeline_days: Number(days) } : {}),
        },
      });
      onSent();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.replyBox}>
      {error ? <Banner kind="error">{error}</Banner> : null}
      <Field
        label={t("campaign.replyNote")}
        value={note}
        onChangeText={setNote}
        multiline
        numberOfLines={3}
        maxLength={NOTE_MAX_LENGTH}
        placeholder={t("campaign.replyNotePlaceholder")}
      />
      <View style={{ flexDirection: "row", gap: space(2) }}>
        <View style={{ flex: 1 }}>
          <Field
            label={t("campaign.replyRate")}
            value={rate}
            onChangeText={(v) => setRate(v.replace(/\D/g, ""))}
            keyboardType="number-pad"
            placeholder={ratePlaceholder}
          />
        </View>
        <View style={{ flex: 1 }}>
          <Field
            label={t("campaign.replyDays")}
            value={days}
            onChangeText={(v) => setDays(v.replace(/\D/g, ""))}
            keyboardType="number-pad"
            placeholder={daysPlaceholder}
          />
        </View>
      </View>
      <Hint>{t("campaign.replyHint")}</Hint>
      <View style={{ height: space(2) }} />
      <PrimaryButton
        title={busy ? t("common.working") : t("campaign.replySend")}
        onPress={submit}
        loading={busy}
        disabled={!note.trim()}
      />
    </View>
  );
}

/* A negotiation read as a thread: every round in order, the live offer at the
   bottom carrying the emphasis and the buttons. Only the latest version can
   be accepted — everything above it has already been superseded by whoever
   wrote the row underneath, and signing a withdrawn offer would put terms in
   a contract that neither side is still standing behind.

   The turn badge is the mirror image of the one the creator reads on their
   invitations page, off the same author_role field: "the creator replied" is
   this reader's turn to act, "waiting on the creator" is not. */
export function ProposalThread({ campaignId, chain, disabled, onAccept, onViewContract, onReplied }: {
  campaignId: string;
  chain: ProposalChain;
  disabled: boolean;
  onAccept: (proposalId: string) => void;
  onViewContract: (proposalId: string) => void;
  onReplied: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [replyOpen, setReplyOpen] = useState(false);
  const latest = chain.latest;
  const awaitingCreator = latest.author_role === "business";

  return (
    <View style={styles.wrap}>
      <View style={styles.headRow}>
        <Text style={styles.creator} numberOfLines={1}>
          {latest.display_name || t("campaign.unnamedCreator")}
          {latest.top_follower_count
            ? `  ·  ${latest.top_follower_count.toLocaleString(i18n.language)}`
            : ""}
        </Text>
        {latest.status === "submitted" ? (
          <Text style={[styles.turn, awaitingCreator ? styles.turnTheirs : styles.turnYours]}>
            {awaitingCreator ? t("campaign.awaitingCreator") : t("campaign.creatorReplied")}
          </Text>
        ) : null}
      </View>

      <View style={{ gap: space(2), marginTop: space(2) }}>
        {chain.versions.map((v) => {
          const isLatest = v.id === latest.id;
          return (
            <View key={v.id} style={[styles.version, isLatest && styles.versionLive]}>
              <View style={styles.versionHead}>
                <Text style={styles.versionAuthor}>
                  {v.author_role === "business" ? t("campaign.authorBrand") : t("campaign.authorCreator")}
                </Text>
                <Text style={styles.versionMeta}>
                  {isLatest ? `${t("campaign.currentOffer")} · ` : ""}v{v.version}
                </Text>
              </View>
              <Text style={[styles.versionTerms, isLatest && { fontWeight: "700" }]}>
                {v.rate_amount} {v.rate_currency} · {v.timeline_days} {t("campaign.daysShort")}
              </Text>
              {v.note ? <Text style={styles.versionNote}>{v.note}</Text> : null}
            </View>
          );
        })}
      </View>

      {latest.status === "submitted" ? (
        <View style={{ marginTop: space(3), gap: space(2) }}>
          <PrimaryButton
            title={t("campaign.accept")}
            onPress={() => onAccept(latest.id)}
            disabled={disabled}
          />
          <GhostButton
            title={t("campaign.reply")}
            onPress={() => setReplyOpen((o) => !o)}
            disabled={disabled}
          />
        </View>
      ) : latest.status === "accepted" ? (
        <View style={{ marginTop: space(3) }}>
          <GhostButton
            title={t("campaign.viewContract")}
            onPress={() => onViewContract(latest.id)}
            disabled={disabled}
          />
        </View>
      ) : null}

      {replyOpen && latest.status === "submitted" ? (
        <ReplyForm
          campaignId={campaignId}
          latestId={latest.id}
          ratePlaceholder={String(latest.rate_amount)}
          daysPlaceholder={String(latest.timeline_days)}
          onSent={() => {
            setReplyOpen(false);
            onReplied();
          }}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { borderTopWidth: 1, borderTopColor: colors.line, paddingTop: space(3), marginTop: space(3) },
  headRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space(2), flexWrap: "wrap" },
  creator: { fontSize: font.body, fontWeight: "700", color: colors.ink, flexShrink: 1 },
  turn: {
    fontSize: font.tiny,
    fontWeight: "700",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
    overflow: "hidden",
  },
  turnYours: { color: colors.white, backgroundColor: colors.teal600 },
  turnTheirs: { color: colors.muted, backgroundColor: colors.surface2 },
  version: {
    borderLeftWidth: 3,
    borderLeftColor: colors.line,
    paddingHorizontal: space(3),
    paddingVertical: space(2),
  },
  versionLive: { borderLeftColor: colors.indigo, backgroundColor: colors.surface2, borderRadius: radius.sm },
  versionHead: { flexDirection: "row", justifyContent: "space-between", gap: space(2) },
  versionAuthor: { fontSize: font.tiny, fontWeight: "700", color: colors.ink },
  versionMeta: { fontSize: font.tiny, color: colors.indigo, fontWeight: "600" },
  versionTerms: { fontSize: font.small, color: colors.ink, marginTop: 2 },
  versionNote: { fontSize: font.tiny, color: colors.muted, marginTop: 3 },
  replyBox: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
    marginTop: space(3),
  },
});
