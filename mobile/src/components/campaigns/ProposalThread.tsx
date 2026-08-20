import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { useAuth } from "../../lib/auth";
import type { ProposalChain } from "../../lib/campaignTypes";
/* Side-effect import: registers the campaign.reject* copy the control
   below reads. Without it this thread renders raw keys at the buyer. */
import "../../lib/rejectionStrings";
import { Banner, Field, GhostButton, Hint, PrimaryButton } from "../ui";
import { colors, family, font, radius, space } from "../../theme";

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
   this reader's turn to act, "waiting on the creator" is not.

   THREE ANSWERS, AND THEIR WEIGHTS ARE THE PRODUCT'S OPINION, the same one
   web/src/pages/CampaignDetail.tsx states. Accept is primary because it is
   what a brief is for. Reply is next, because a number that is wrong is
   usually a number to argue about and every argument that leaves this screen
   leaves the platform. Reject is last and quietest — a text link rather than
   a third full-width button — because it is the least-used of the three and
   the only one that cannot be undone, so it is offered plainly, sized down,
   and behind a confirmation that says so. */
export function ProposalThread({ campaignId, chain, disabled, rejectable, onAccept, onViewContract, onReplied, onRejected }: {
  campaignId: string;
  chain: ProposalChain;
  disabled: boolean;
  /* Off campaign.is_direct, mirroring the server. A direct order is closed by
     the creator declining it — which also cancels the order and tells the
     buyer they were not charged — so rejecting a version of one would leave
     it half-closed, and campaigns/rejections.py refuses it with
     proposal_is_direct_order. The control is removed rather than left to be
     refused, exactly as the invitation withdraw link is. */
  rejectable: boolean;
  onAccept: (proposalId: string) => void;
  onViewContract: (proposalId: string) => void;
  onReplied: () => void;
  onRejected: () => void;
}) {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const [replyOpen, setReplyOpen] = useState(false);
  /* Per thread rather than shared, so a buyer with four bids open is never
     unsure which one they are about to end. */
  const [confirmingReject, setConfirmingReject] = useState(false);
  const [rejectBusy, setRejectBusy] = useState(false);
  const [rejectError, setRejectError] = useState<string | null>(null);
  const latest = chain.latest;
  const awaitingCreator = latest.author_role === "business";

  /* Turning the live offer down. Addressed to the latest version's id, which
     is the only one the server will act on: it closes the live version of
     this creator's chain and nothing above it.

     ITS OWN BUSY AND ERROR STATE, not the screen's — the reason
     ContractDetailScreen keeps its cancel card out of the page banner. That
     banner sits at the top of a long campaign screen, several thumb scrolls
     above this thread, so a refusal landing up there would read from this
     seat as a control that did nothing. */
  async function reject() {
    setRejectBusy(true);
    setRejectError(null);
    try {
      await api(`/campaigns/${campaignId}/proposals/${latest.id}/reject`, { method: "POST", token });
      setConfirmingReject(false);
      /* The screen reloads the campaign, so this thread comes straight back
         with the chain closed — no turn badge, no answers — rather than
         waiting for a pull-to-refresh to admit what just happened. */
      onRejected();
    } catch (e) {
      /* Off the CODE the refusal carries, through errorText, and every one of
         them is already written in both languages: `proposal_closed` if the
         chain moved on in another session, `proposal_has_contract` if it has
         already produced one, `campaign_not_open` on a brief that ended while
         this screen was open. Each is a different thing to do next, and the
         400 they share names none of them. */
      setRejectError(errorText(e, t));
    } finally {
      setRejectBusy(false);
    }
  }

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
              <Text style={[styles.versionTerms, isLatest && { fontFamily: family.bodyBold }]}>
                {v.rate_amount} {v.rate_currency} · {v.timeline_days} {t("campaign.daysShort")}
              </Text>
              {v.note ? <Text style={styles.versionNote}>{v.note}</Text> : null}
            </View>
          );
        })}
      </View>

      {latest.status === "submitted" ? (
        confirmingReject ? (
          /* The confirmation REPLACES the answers rather than sitting under
             them, which is how both of this negotiation's other inline
             confirmations behave — the campaign acts on CampaignDetailScreen
             and decline/withdraw in the creator's Negotiation. On a 360 dp
             screen a question with the answers to something else still live
             beside it is a question somebody taps past. */
          <View style={{ marginTop: space(3) }}>
            {rejectError ? <Banner kind="error">{rejectError}</Banner> : null}
            {/* Not a Hint: this is the last thing read before an irreversible
                tap, so it gets body ink and body size rather than the muted
                12 pt every other aside on this screen uses. */}
            <Text style={styles.confirm}>{t("campaign.rejectConfirm")}</Text>
            <View style={{ height: space(2) }} />
            <PrimaryButton
              title={rejectBusy ? t("common.working") : t("campaign.rejectYes")}
              onPress={() => void reject()}
              loading={rejectBusy}
              disabled={disabled}
            />
            <View style={{ height: space(2) }} />
            <GhostButton
              title={t("campaign.rejectNo")}
              onPress={() => {
                setConfirmingReject(false);
                setRejectError(null);
              }}
              disabled={rejectBusy}
            />
          </View>
        ) : (
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
            {/* TWO TAPS, ALWAYS: the first one only asks. This ends the
                negotiation for good and tells the creator, and a thumb on a
                phone is not a precise instrument. */}
            {rejectable ? (
              <Text
                style={[styles.reject, disabled && styles.rejectOff]}
                accessibilityRole="button"
                onPress={
                  disabled
                    ? undefined
                    : () => {
                        setConfirmingReject(true);
                        setRejectError(null);
                      }
                }
              >
                {t("campaign.reject")}
              </Text>
            ) : null}
          </View>
        )
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
  creator: { fontSize: font.body, fontFamily: family.bodyBold, color: colors.ink, flexShrink: 1 },
  turn: {
    fontSize: font.tiny,
    fontFamily: family.bodyBold,
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
  versionAuthor: { fontSize: font.tiny, fontFamily: family.bodyBold, color: colors.ink },
  versionMeta: { fontSize: font.tiny, color: colors.indigo, fontFamily: family.bodySemi },
  versionTerms: { fontFamily: family.body, fontSize: font.small, color: colors.ink, marginTop: 2 },
  versionNote: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 3 },
  /* Visually secondary to Accept and Reply, as on web, and a text link rather
     than a third GhostButton for the reason web sizes its own reject button
     down: a control shaped like the two decisions beside it reads as a third
     decision of equal weight. Muted rather than the withdraw link's red — a
     rejection is an answer, not a warning — and the vertical padding is the
     touch target, because a line of 14 pt text is not one. */
  reject: {
    fontSize: font.small,
    fontFamily: family.bodySemi,
    color: colors.muted,
    textAlign: "center",
    paddingVertical: space(2),
  },
  rejectOff: { opacity: 0.6 },
  /* The confirmation sentence, in ink at body size: see the comment where it
     is rendered. */
  confirm: { fontFamily: family.body, fontSize: font.small, color: colors.ink, lineHeight: 20 },
  replyBox: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
    marginTop: space(3),
  },
});
