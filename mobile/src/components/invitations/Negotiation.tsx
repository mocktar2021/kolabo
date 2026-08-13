import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { useAuth } from "../../lib/auth";
import { orderTimeLeft, sentParts } from "../../lib/orders";
import type { Proposal } from "../../lib/campaignTypes";
import type { Contract } from "../../lib/contractTypes";
import { Banner, Field, GhostButton, Hint, PrimaryButton } from "../ui";
import { colors, family, font, radius, space } from "../../theme";

/* Mirrors MAX_NOTE_LENGTH in backend/app/modules/campaigns/schemas.py, so the
   limit is hit as a full field rather than as a 422 after typing. */
const NOTE_MAX_LENGTH = 2000;

/* The creator's answer with different numbers on it. There is no creator-side
   counter endpoint and there does not need to be one: the next version in the
   chain IS the counter, so this posts to the same submit path a brief's first
   proposal takes. Currency is not counterable — a chain is priced in one
   currency or it is two negotiations pretending to be one — so the counter
   repeats the currency already on the table. Prefilled with the live terms:
   the creator is almost always changing one of the two numbers. */
function CounterForm({ campaignId, live, isOrder, onSent }: {
  campaignId: string;
  live: Proposal;
  isOrder: boolean;
  onSent: () => void;
}) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rate, setRate] = useState(String(live.rate_amount));
  const [days, setDays] = useState(String(live.timeline_days));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!rate || !days) return;
    setBusy(true);
    setError(null);
    try {
      const trimmed = note.trim();
      await api(`/campaigns/${campaignId}/proposals`, {
        method: "POST",
        token,
        body: {
          rate_amount: Number(rate),
          rate_currency: live.rate_currency,
          timeline_days: Number(days),
          ...(trimmed ? { note: trimmed } : {}),
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
    <View style={styles.counterBox}>
      {error ? <Banner kind="error">{error}</Banner> : null}
      <View style={{ flexDirection: "row", gap: space(2) }}>
        <View style={{ flex: 1 }}>
          <Field
            label={`${t("invitation.rate")} (${live.rate_currency})`}
            value={rate}
            onChangeText={(v) => setRate(v.replace(/\D/g, ""))}
            keyboardType="number-pad"
          />
        </View>
        <View style={{ flex: 1 }}>
          <Field
            label={t("invitation.days")}
            value={days}
            onChangeText={(v) => setDays(v.replace(/\D/g, ""))}
            keyboardType="number-pad"
          />
        </View>
      </View>
      <Field
        label={t("invitation.note")}
        value={note}
        onChangeText={setNote}
        multiline
        numberOfLines={3}
        maxLength={NOTE_MAX_LENGTH}
        placeholder={t("invitation.notePlaceholder")}
      />
      {isOrder ? <Hint>{t("invitation.counterHint")}</Hint> : null}
      <View style={{ height: space(2) }} />
      <PrimaryButton
        title={busy ? t("common.working") : t("invitation.counterSend")}
        onPress={submit}
        loading={busy}
        disabled={!rate || !days}
      />
    </View>
  );
}

/* Whose turn it is, what the other side actually said, and what the creator
   may DO about it. The asymmetry of the buttons is the backend's, not a
   styling choice:

     - Accept exists only on a direct order whose live version is the brand's.
       A brief's proposals are accepted by the BUSINESS through the contracts
       path, and accepting one's own counter is a 400 — a button that exists
       only to be refused is worse than no button.
     - Decline stays on an open order whichever side holds the live version.
     - Withdraw is the BRIEF-side mirror of decline: a brief only, the
       creator's own live version only, still open. Withdrawn is not declined
       — nobody said no — which is why the two endpoints exist separately.
     - Counter is available on both kinds of row: the next version in the
       chain, on the order's original clock.

   The turn is DERIVED from the live version's author_role, never stored:
   one side wrote the last word and there is exactly one of those, so a
   stored "waiting_on" would only ever be a second copy that could drift. */
export function Negotiation({ campaignId, live, history, isOrder, readOnly = false, onDone, onContract }: {
  campaignId: string;
  live: Proposal;
  history: Proposal[];
  isOrder: boolean;
  /* True when the campaign underneath is no longer open (cancelled): the
     thread stays readable — it is the record of what was offered — but every
     action goes, because the backend would refuse it with campaign_not_open
     and a button that only ever earns a refusal is a trap. */
  readOnly?: boolean;
  onDone: () => void;
  onContract: (contractId: string) => void;
}) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [counterOpen, setCounterOpen] = useState(false);
  const [confirming, setConfirming] = useState<"decline" | "withdraw" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const left = live.expires_at ? orderTimeLeft(live.expires_at) : null;
  const expired = isOrder && left === null;
  const open = live.status === "submitted" && !readOnly;
  const theirMove = live.author_role === "business";
  const versions = history.length > 0 ? history : [live];
  const withdrawable = !isOrder && open && !theirMove;

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      /* Accepting is what creates the contract — the endpoint returns it, and
         signing is the next thing both sides have to do, so that is where the
         creator goes. Money still has not moved: escrow is funded by the
         buyer after both signatures. */
      const contract = await api<Contract>(`/campaigns/orders/${live.id}/accept`, {
        method: "POST",
        token,
      });
      onContract(contract.id);
    } catch (e) {
      setError(errorText(e, t));
      setBusy(false);
    }
  }

  async function decline() {
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/orders/${live.id}/decline`, { method: "POST", token });
      onDone();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function withdraw() {
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/proposals/${live.id}/withdraw`, { method: "POST", token });
      onDone();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.headRow}>
        <Text style={styles.title}>{t("invitation.negotiationTitle")}</Text>
        {open ? (
          <Text style={[styles.turn, theirMove ? styles.turnYours : styles.turnTheirs]}>
            {theirMove ? t("invitation.turnYours") : t("invitation.turnBrand")}
          </Text>
        ) : null}
      </View>

      {/* The whole exchange, oldest first, live version marked. Every round
          and not just the last: a counter is an answer to something, and a
          creator shown the answer without the question is being asked to
          price a conversation they cannot read. */}
      <View style={{ gap: space(2), marginTop: space(2) }}>
        {versions.map((v) => {
          const isLive = v.id === live.id;
          const fromBrand = v.author_role === "business";
          const when = v.created_at ? sentParts(v.created_at) : null;
          return (
            <View key={v.id} style={[styles.version, isLive && styles.versionLive]}>
              <View style={styles.versionHead}>
                <Text style={styles.versionAuthor}>
                  {fromBrand ? t("campaign.authorBrand") : t("campaign.authorCreator")}
                </Text>
                <Text style={styles.versionMeta}>
                  {isLive ? `${t("campaign.currentOffer")} · ` : ""}v{v.version}
                </Text>
              </View>
              <Text style={[styles.versionTerms, isLive && { fontFamily: family.bodyBold }]}>
                {v.rate_amount} {v.rate_currency} · {v.timeline_days} {t("campaign.daysShort")}
              </Text>
              {v.note ? <Text style={styles.versionNote}>{v.note}</Text> : null}
              {when ? <Text style={styles.versionWhen}>{t(when.key, { n: when.n })}</Text> : null}
            </View>
          );
        })}
      </View>

      {/* The clock, orders only — a brief's proposal has nothing to count
          down. Hours while there is a day left, minutes in the last stretch. */}
      {isOrder ? (
        <Text style={[styles.clock, expired && { fontFamily: family.bodyBold }]}>
          {expired || left === null
            ? t("invitation.orderExpired")
            : left.unit === "hours"
              ? t("invitation.orderExpiresHours", { n: left.n })
              : t("invitation.orderExpiresMinutes", { n: left.n })}
        </Text>
      ) : null}

      {error ? <Banner kind="error">{error}</Banner> : null}

      {open ? (
        confirming === "decline" ? (
          <View style={{ marginTop: space(3) }}>
            {/* Inline, never a system alert: the sentence that makes this an
                easy decision — nobody has been charged — has to be readable
                and translated. */}
            <Hint>{t("invitation.orderDeclineConfirm")}</Hint>
            <View style={{ height: space(2) }} />
            <GhostButton title={t("invitation.orderDeclineYes")} onPress={decline} disabled={busy} />
            <View style={{ height: space(2) }} />
            <GhostButton title={t("invitation.orderDeclineNo")} onPress={() => setConfirming(null)} disabled={busy} />
          </View>
        ) : confirming === "withdraw" ? (
          <View style={{ marginTop: space(3) }}>
            <Hint>{t("invitation.withdrawConfirm")}</Hint>
            <View style={{ height: space(2) }} />
            <GhostButton title={t("invitation.withdrawYes")} onPress={withdraw} disabled={busy} />
            <View style={{ height: space(2) }} />
            <GhostButton
              title={t("invitation.withdrawNo")}
              onPress={() => {
                setConfirming(null);
                setError(null);
              }}
              disabled={busy}
            />
          </View>
        ) : (
          <View style={{ marginTop: space(3), gap: space(2) }}>
            {isOrder && theirMove ? (
              <PrimaryButton
                title={busy ? t("common.working") : t("invitation.orderAccept")}
                onPress={accept}
                loading={busy}
                disabled={expired}
              />
            ) : null}
            {isOrder ? (
              <GhostButton
                title={t("invitation.orderDecline")}
                onPress={() => setConfirming("decline")}
                disabled={busy || expired}
              />
            ) : null}
            {withdrawable ? (
              <GhostButton
                title={t("invitation.withdraw")}
                onPress={() => {
                  setConfirming("withdraw");
                  setError(null);
                }}
                disabled={busy}
              />
            ) : null}
            {theirMove && !expired ? (
              <GhostButton
                title={t("invitation.counter")}
                onPress={() => setCounterOpen((o) => !o)}
                disabled={busy}
              />
            ) : null}
          </View>
        )
      ) : null}

      {counterOpen && open && theirMove && !expired ? (
        <CounterForm
          campaignId={campaignId}
          live={live}
          isOrder={isOrder}
          onSent={() => {
            setCounterOpen(false);
            onDone();
          }}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { borderTopWidth: 1, borderTopColor: colors.line, marginTop: space(3), paddingTop: space(3) },
  counterBox: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
    marginTop: space(3),
  },
  headRow: { flexDirection: "row", alignItems: "center", gap: space(2), flexWrap: "wrap" },
  title: { fontSize: font.small, fontFamily: family.bodyBold, color: colors.ink },
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
  versionWhen: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 3 },
  clock: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: space(3) },
});
