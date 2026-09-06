import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/dates";
import { directOrderOf } from "../lib/orders";
import { PLATFORM_LABELS, deliverableLabel } from "../lib/platforms";
import type { InvitationWithCampaign } from "../lib/campaignTypes";
import { ListFilter, type FilterOption } from "../components/lists";
import { Negotiation } from "../components/invitations/Negotiation";
import { Banner, Field, GhostButton, Hint, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
import { colors, family, font, radius, space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

const CURRENCIES = ["XOF", "XAF", "GHS", "NGN"];
const NOTE_MAX_LENGTH = 2000;

/* A brief nobody has priced yet: the creator's first proposal. The note
   travels with the offer rather than in a message beside it, so the terms and
   the reasoning for them stay in one record — the same record the business
   answers and the contract is eventually written from. */
function ProposalForm({ campaignId, onDone }: { campaignId: string; onDone: () => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rate, setRate] = useState("");
  const [currency, setCurrency] = useState("XOF");
  const [days, setDays] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

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
          rate_currency: currency,
          timeline_days: Number(days),
          ...(trimmed ? { note: trimmed } : {}),
        },
      });
      setDone(true);
      onDone();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  if (done) return <Banner kind="success">{t("invitation.proposalSent")}</Banner>;

  return (
    <View>
      {error ? <Banner kind="error">{error}</Banner> : null}
      <View style={{ flexDirection: "row", gap: space(2) }}>
        <View style={{ flex: 1 }}>
          <Field
            label={t("invitation.rate")}
            value={rate}
            onChangeText={(v) => setRate(v.replace(/\D/g, ""))}
            keyboardType="number-pad"
            placeholder="40000"
          />
        </View>
        <View style={{ flex: 1 }}>
          <Field
            label={t("invitation.days")}
            value={days}
            onChangeText={(v) => setDays(v.replace(/\D/g, ""))}
            keyboardType="number-pad"
            placeholder="7"
          />
        </View>
      </View>
      <Text style={styles.fieldLabel}>{t("campaign.currency")}</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space(2), marginBottom: space(3) }}>
        {CURRENCIES.map((c) => (
          <Text
            key={c}
            onPress={() => setCurrency(c)}
            style={[styles.currencyChip, currency === c && styles.currencyChipOn]}
          >
            {c}
          </Text>
        ))}
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
      <PrimaryButton
        title={busy ? t("common.working") : t("invitation.send")}
        onPress={submit}
        loading={busy}
        disabled={!rate || !days}
      />
    </View>
  );
}

/* One invitation, read top to bottom the way the decision is actually made:
   who is asking, what they want made, what they budgeted, by when — and only
   at the bottom, what the creator wants to be paid. Two kinds of row share
   this card: a live proposal carrying expires_at is a direct order (the offer
   is already on the table); anything else is a brief to price. */
function InvitationCard({ inv, onDone, onContract }: {
  inv: InvitationWithCampaign;
  onDone: () => void;
  onContract: (contractId: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const c = inv.campaign;
  const order = directOrderOf(inv);
  const live = inv.proposal;
  /* A creator only ever sees published and cancelled campaigns; a cancelled
     one keeps its card (the record of what was offered) but takes no more
     answers — the badge says why the forms are gone, instead of leaving a
     button that could only earn the backend's campaign_not_open refusal. */
  const cancelled = c.status === "cancelled";

  return (
    <View style={styles.card}>
      <Text style={styles.brand}>{inv.business_company_name || t("invitation.brandFallback")}</Text>
      <View style={styles.titleRow}>
        <Text style={styles.cardTitle} numberOfLines={2}>{c.title}</Text>
        {order ? <Text style={styles.orderBadge}>{t("invitation.orderBadge")}</Text> : null}
        {cancelled ? <Text style={styles.cancelledBadge}>{t("invitation.campaignCancelled")}</Text> : null}
      </View>
      <Text style={styles.status}>{t(`invitation.status_${inv.status}`, { defaultValue: inv.status })}</Text>

      {/* A brief is priced against a budget and a deadline. An order has
          neither to argue about: the price is already named and the timeline
          is on the offer below. */}
      {!order ? (
        <Text style={styles.meta}>
          {t("campaign.budget")}:{" "}
          {c.budget_amount
            ? `${c.budget_amount.toLocaleString(i18n.language)} ${c.budget_currency ?? ""}`.trim()
            : t("campaign.noBudget")}
          {"  ·  "}
          {t("campaign.deadline")}:{" "}
          {c.deadline ? formatDate(c.deadline, i18n.language) : t("invitation.noDeadline")}
        </Text>
      ) : null}

      <Text style={styles.delivTitle}>{t("campaign.deliverables")}</Text>
      {c.deliverables.length === 0 ? (
        <Hint>{t("campaign.noDeliverables")}</Hint>
      ) : (
        <View style={{ gap: 2 }}>
          {c.deliverables.map((d, i) => (
            <Text key={i} style={styles.deliv}>
              {d.quantity} × {deliverableLabel(d.type)} · {PLATFORM_LABELS[d.platform] ?? d.platform}
            </Text>
          ))}
        </View>
      )}

      {live ? (
        <Negotiation
          campaignId={inv.campaign_id}
          live={live}
          history={inv.proposal_history ?? []}
          isOrder={order !== null}
          readOnly={cancelled}
          onDone={onDone}
          onContract={onContract}
        />
      ) : cancelled ? null : (
        <View style={styles.proposalWrap}>
          <Text style={styles.delivTitle}>{t("invitation.yourProposal")}</Text>
          <ProposalForm campaignId={inv.campaign_id} onDone={onDone} />
        </View>
      )}
    </View>
  );
}

export default function InvitationsScreen({ navigation }: AppScreenProps<"Invitations">) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [invitations, setInvitations] = useState<InvitationWithCampaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  /* "" is all. Narrows on the invitation status the creator already reads on
     each card; filtered in memory. */
  const [statusFilter, setStatusFilter] = useState("");

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      setInvitations(await api<InvitationWithCampaign[]>("/campaigns/invitations/mine", { token }));
      setError(null);
    } catch (e) {
      setError(errorText(e, t));
    }
  }, [token, t]);

  // Reload on focus so an order answered elsewhere shows its real state.
  useEffect(() => navigation.addListener("focus", () => void load()), [navigation, load]);
  useEffect(() => {
    void load();
  }, [load]);

  const loading = invitations === null;
  const empty = !loading && invitations.length === 0;
  const statusOptions: FilterOption[] = Array.from(
    new Set((invitations ?? []).map((i) => i.status))
  ).map((s) => ({ value: s, label: t(`invitation.status_${s}`, { defaultValue: s }) }));
  const shown = statusFilter
    ? (invitations ?? []).filter((i) => i.status === statusFilter)
    : invitations ?? [];

  return (
    <Screen
      loading={invitations === null && !error}
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void load().finally(() => setRefreshing(false));
      }}
    >
      <Title>{t("invitation.title")}</Title>
      <Subtitle>{t("invitation.sub")}</Subtitle>

      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <View style={{ marginBottom: space(3) }}>
            <GhostButton title={t("common.retry")} onPress={() => void load()} />
          </View>
        </>
      ) : null}

      {!loading && !empty ? (
        <View style={{ marginBottom: space(3) }}>
          <ListFilter options={statusOptions} value={statusFilter} onChange={setStatusFilter} />
        </View>
      ) : null}

      {loading ? null : empty ? (
        <>
          <Text style={{ fontFamily: family.body, color: colors.ink, fontSize: font.body }}>{t("invitation.empty")}</Text>
          <Hint>{t("invitation.emptyHint")}</Hint>
        </>
      ) : shown.length === 0 ? (
        <Hint>{t("lf.none")}</Hint>
      ) : (
        <View style={{ gap: space(3) }}>
          {shown.map((inv) => (
            <InvitationCard
              key={inv.id}
              inv={inv}
              onDone={() => void load()}
              onContract={(id) => navigation.navigate("ContractDetail", { id })}
            />
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
  brand: {
    fontSize: font.tiny,
    fontFamily: family.bodyBold,
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  titleRow: { flexDirection: "row", alignItems: "center", gap: space(2), flexWrap: "wrap", marginTop: 2 },
  cardTitle: { fontSize: font.h2, fontFamily: family.display, color: colors.ink, flexShrink: 1 },
  orderBadge: {
    fontSize: font.tiny,
    fontFamily: family.bodyBold,
    color: colors.white,
    backgroundColor: colors.indigo,
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
    overflow: "hidden",
  },
  cancelledBadge: {
    fontSize: font.tiny,
    fontFamily: family.bodyBold,
    color: "#9b2c2c",
    backgroundColor: "#fdecec",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
    overflow: "hidden",
  },
  status: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 3 },
  meta: { fontFamily: family.body, fontSize: font.small, color: colors.ink, marginTop: space(2) },
  delivTitle: { fontSize: font.small, fontFamily: family.bodyBold, color: colors.ink, marginTop: space(3), marginBottom: space(1) },
  deliv: { fontFamily: family.body, fontSize: font.small, color: colors.ink },
  proposalWrap: { borderTopWidth: 1, borderTopColor: colors.line, marginTop: space(3), paddingTop: space(1) },
  fieldLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) },
  currencyChip: {
    fontSize: font.small,
    fontFamily: family.bodySemi,
    color: colors.ink,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(2),
    overflow: "hidden",
  },
  currencyChipOn: { color: colors.teal600, borderColor: colors.teal, backgroundColor: colors.tealSoft },
});
