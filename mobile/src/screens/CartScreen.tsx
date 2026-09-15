import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { Ionicons } from "@expo/vector-icons";
import { ApiError, api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { isBusinessLike, useAuth } from "../lib/auth";
import { useCart } from "../lib/cart";
import {
  checkoutItem,
  groupByCreator,
  totalsByCurrency,
  type CartCheckoutOrder,
  type CartCheckoutResult,
  type CartLine,
} from "../lib/cartTotals";
import { formatAmount } from "../lib/money";
import { PLATFORM_LABELS, deliverableLabel } from "../lib/platforms";
import { Banner, Card, GhostButton, Hint, PrimaryButton, Screen, SectionTitle } from "../components/ui";
import { colors, family, font, radius, space } from "../theme";
/* Side-effect import: registers the cart.* and public.* copy on the i18n
   instance. Without it every label on this screen renders as its raw key —
   and RootNavigator's `title: t("cart.title")` depends on this module being
   pulled in by importing this screen. */
import "../lib/cartStrings";
import type { AppScreenProps } from "../navigation/types";

/* The basket, and the one request that turns it into orders.

   WHAT THE ENDPOINT DOES WITH IT, because the screen has to show the same
   shape: POST /campaigns/orders/checkout takes a flat list of items, groups
   them by creator, and FANS OUT into one direct order per creator — each
   accepted or declined on its own, on its own clock, for its own money. So
   three packs from one person are one order with three deliverables; two
   people are two independent orders. backend/app/modules/campaigns/cart.py
   argues all of it.

   IT IS ALL OR NOTHING. Every item is validated before a single row is
   written and the writes are one transaction, so a refused line means NOTHING
   was ordered — not "the first two went through". That is said out loud next
   to the error, because a buyer who assumes otherwise re-orders the first
   two.

   WHICH IS EXACTLY WHY THE TICK IS A SELECTION AND NOT A PARTIAL ORDER. The
   server cannot create part of a basket, so choosing less means SENDING less;
   what goes up still goes up whole. And the tick is PER CREATOR rather than
   per line, because the creator's order is the unit the server creates:
   ticking two of somebody's three packs would look like a choice and would
   arrive as one order for two — the same order, quietly different. Somebody
   who wants only two removes the third.

   NO RULE IS RESTATED HERE. The item ceiling, the price floor, the quantity
   and timeline ranges, one currency per creator, ordering from yourself —
   every one of them is the server's, and every refusal arrives with a code
   that lib/errorMessages turns into the reader's language. A second copy on
   this screen would be the copy that drifts, and the drift would be about
   money. */

type Selection = Set<string>;

export default function CartScreen({ navigation }: AppScreenProps<"Cart">) {
  const { t, i18n } = useTranslation();
  const { token, role } = useAuth();
  const { lines, loading, remove } = useCart();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /* Which line the server refused, by ID rather than by position. The index
     the server sends back is the position in WHAT WAS POSTED, which stops
     being the position on screen as soon as anything is unticked — and
     highlighting the wrong line is worse than highlighting none, because the
     buyer then edits an item the server never complained about. Resolved once,
     through the frozen list that was actually sent. */
  const [rejectedId, setRejectedId] = useState<string | null>(null);
  const [orders, setOrders] = useState<CartCheckoutOrder[] | null>(null);
  /* The lines that became those orders. Kept because they leave the basket on
     success and the receipt still has to name who each order is for. */
  const [orderedLines, setOrderedLines] = useState<CartLine[]>([]);

  /* WHAT IS **NOT** SELECTED, rather than what is. Default-all-selected is the
     requirement, and storing the negative is what makes it true without any
     syncing: a pile added after this state was created is selected because it
     is not in the set, so adding a pack on another profile and coming back
     does not silently leave it out of the order. A positive set would have to
     be topped up every time the basket changed, and the day somebody forgot,
     the bug would be a paid order missing a line. */
  const [deselected, setDeselected] = useState<Selection>(new Set());

  const money = (n: number, currency: string) => formatAmount(n, currency, i18n.language);

  const groups = groupByCreator(lines);
  const selectedGroups = groups.filter((g) => !deselected.has(g.creator_user_id));
  const selectedLines = selectedGroups.flatMap((g) => g.lines);
  const selectedTotals = totalsByCurrency(selectedLines);

  function toggleGroup(creatorUserId: string) {
    setDeselected((prev) => {
      const next = new Set(prev);
      if (next.has(creatorUserId)) next.delete(creatorUserId);
      else next.add(creatorUserId);
      return next;
    });
  }

  function creatorName(displayName: string | null): string {
    /* NOT "creator with no name". A line added before the basket kept the
       identity carries none because nobody ever asked, and telling a buyer
       this person is nameless would assert something we never checked. The
       neutral label is the honest floor for both cases. */
    return displayName || t("cart.unknownCreator");
  }

  async function checkout() {
    /* Frozen before the request. selectedLines is derived from state a tap
       could change while the round trip is in flight, and the index the server
       sends back has to be resolved against exactly what was sent. */
    const posted = selectedLines;
    if (posted.length === 0) return;
    setBusy(true);
    setError(null);
    setRejectedId(null);
    try {
      const res = await api<CartCheckoutResult>("/campaigns/orders/checkout", {
        method: "POST",
        token,
        body: { items: posted.map(checkoutItem) },
      });
      setOrders(res.orders);
      setOrderedLines(posted);
      /* Only what was ordered leaves the basket. Clearing the whole thing
         would throw away the piles the buyer deliberately held back, which is
         the one thing holding them back was for. */
      posted.forEach((line) => remove(line.id));
    } catch (e) {
      /* THE POSITION ARRIVES AS DATA, in values.cart_index, and is ZERO-BASED
         (cart.py enumerates from zero). Read as a number rather than out of
         the English sentence, so rewording that sentence in either language
         cannot silently stop the highlight working.

         Number(null) is 0, which would confidently highlight the first row of
         a basket the server never said anything about — hence the integer
         test rather than a truthiness one. */
      if (e instanceof ApiError) {
        const raw = e.values?.cart_index;
        const index = raw == null ? NaN : Number(raw);
        if (Number.isInteger(index)) setRejectedId(posted[index]?.id ?? null);
      }
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  /* The cart is the buying side's, exactly as the API is: checkout runs
     _require_campaign_author and answers 403 (campaign_author_only) to a
     creator. Mobile has no route guards, so the entry points simply do not
     exist for a creator — the tab header button and the storefront buttons are
     both behind isBusinessLike. This says so anyway for the reader who arrives
     some other way: a screen that is blank without explaining itself reads as
     a fault. */
  if (!isBusinessLike(role)) {
    return (
      <Screen>
        <Banner kind="info">{t("cart.brandsOnly")}</Banner>
      </Screen>
    );
  }

  if (orders) {
    return (
      <Screen>
        <Card>
          <Banner kind="success">{t("cart.successTitle")}</Banner>
          <Hint>{t("cart.successRule")}</Hint>
          {/* Anything held back is still in the basket and is still
              orderable. Said here because the success banner otherwise reads
              as "the cart is done". */}
          {lines.length > 0 ? <Hint>{t("cart.remaining", { n: lines.length })}</Hint> : null}
          <View style={{ marginTop: space(3) }}>
            {orders.map((o) => (
              /* One row per ORDER, not per basket line: the buyer sent a flat
                 list and got back a shorter list, and creator_user_id is what
                 tells them apart. Each opens its campaign, which is where a
                 direct order lives until the creator answers — there is no
                 contract to open yet. */
              <View key={o.campaign_id} style={styles.receiptRow}>
                <Text style={styles.receiptName} numberOfLines={2}>
                  {creatorName(
                    orderedLines.find((l) => l.creator_user_id === o.creator_user_id)?.creator
                      .display_name ?? null
                  )}
                </Text>
                <Pressable
                  onPress={() => navigation.navigate("CampaignDetail", { id: o.campaign_id })}
                  hitSlop={8}
                >
                  <Text style={styles.link}>{t("cart.viewOrder")}</Text>
                </Pressable>
              </View>
            ))}
          </View>
          <View style={{ height: space(3) }} />
          {lines.length > 0 ? (
            <GhostButton
              title={t("cart.backToCart")}
              onPress={() => {
                setOrders(null);
                setOrderedLines([]);
              }}
            />
          ) : (
            /* Discover is a TAB and this is a stack screen, so the tab has
               to be named through its host route. A bare navigate("Discover")
               from here is dispatched on the stack, which has no such route,
               and ends up switching the tab underneath a Cart screen that
               stays on top. See TabParamList in navigation/types.ts. */
            <GhostButton
              title={t("cart.emptyCta")}
              onPress={() => navigation.navigate("Tabs", { screen: "Discover" })}
            />
          )}
        </Card>
      </Screen>
    );
  }

  /* The keystore read has not answered yet. Deliberately not the empty state:
     "your cart is empty" is a statement, and it should not be made before
     anybody has looked. */
  if (loading) {
    return (
      <Screen>
        <Hint>{t("cart.loading")}</Hint>
      </Screen>
    );
  }

  if (lines.length === 0) {
    return (
      <Screen>
        <Card>
          <Hint>{t("cart.empty")}</Hint>
          <View style={{ height: space(3) }} />
          {/* Through the host route, for the reason given on the receipt's
              copy of this button above. */}
          <PrimaryButton
            title={t("cart.emptyCta")}
            onPress={() => navigation.navigate("Tabs", { screen: "Discover" })}
          />
        </Card>
      </Screen>
    );
  }

  return (
    <Screen>
      {error ? (
        <Banner kind="error">
          {error}
          {"\n"}
          {t("cart.allOrNothing")}
        </Banner>
      ) : null}

      {/* Only offered once there is more than one pile to choose between.
          "Select all" over a single group is a control that can only ever undo
          itself. */}
      {groups.length > 1 ? (
        <View style={styles.selectRow}>
          <Text style={styles.selectCount}>
            {t("cart.selectedCount", { n: selectedGroups.length, total: groups.length })}
          </Text>
          <Pressable onPress={() => setDeselected(new Set())} hitSlop={6} disabled={busy}>
            <Text style={styles.link}>{t("cart.selectAll")}</Text>
          </Pressable>
          <Pressable
            onPress={() => setDeselected(new Set(groups.map((g) => g.creator_user_id)))}
            hitSlop={6}
            disabled={busy}
          >
            <Text style={styles.link}>{t("cart.selectNone")}</Text>
          </Pressable>
        </View>
      ) : null}

      <View style={{ gap: space(3), marginTop: space(3) }}>
        {groups.map((group) => {
          const selected = !deselected.has(group.creator_user_id);
          const name = creatorName(group.creator.display_name);
          return (
            <View
              key={group.creator_user_id}
              style={[styles.group, !selected && styles.groupExcluded]}
            >
              {/* The tick and the name are one hit target: a 20 dp box on a
                  360 dp screen is a miss waiting to happen. */}
              <Pressable
                onPress={() => toggleGroup(group.creator_user_id)}
                disabled={busy}
                accessibilityRole="checkbox"
                accessibilityState={{ checked: selected }}
                accessibilityLabel={t("cart.selectGroup", { name })}
                style={styles.groupHead}
                hitSlop={4}
              >
                <Ionicons
                  name={selected ? "checkbox" : "square-outline"}
                  size={22}
                  color={selected ? colors.indigo : colors.muted}
                />
                <Text style={styles.groupName} numberOfLines={2}>
                  {name}
                </Text>
              </Pressable>

              {group.lines.map((line) => {
                const isRejected = rejectedId === line.id;
                const meta = [
                  line.package_id ? null : t("cart.custom"),
                  line.platform ? PLATFORM_LABELS[line.platform] ?? line.platform : null,
                  line.deliverable_type ? deliverableLabel(line.deliverable_type) : null,
                  line.quantity && line.quantity > 1 ? t("cart.qty", { n: line.quantity }) : null,
                  line.timeline_days ? t("cart.days", { n: line.timeline_days }) : null,
                ]
                  .filter((part): part is string => !!part)
                  .join(" · ");
                return (
                  <View key={line.id} style={[styles.line, isRejected && styles.lineRejected]}>
                    <View style={styles.lineMain}>
                      {/* Two lines, not one: a pack title in French is
                          routinely longer than 360 dp, and a clipped title is
                          a buyer who cannot tell two packs apart. */}
                      <Text style={styles.lineLabel} numberOfLines={2}>
                        {line.label}
                      </Text>
                      {meta ? <Text style={styles.lineMeta}>{meta}</Text> : null}
                      {line.note ? (
                        <Text style={styles.lineNote}>
                          {t("cart.note")} : {line.note}
                        </Text>
                      ) : null}
                      {/* The refusal sits on the line it is about, not only at
                          the top of the screen: a twenty-line basket with one
                          message above it leaves the buyer counting rows. */}
                      {isRejected && error ? (
                        <Text style={styles.lineRejectedText}>{t("cart.lineRejected")}</Text>
                      ) : null}
                    </View>
                    <View style={styles.lineSide}>
                      <Text style={styles.lineAmount}>{money(line.amount, line.currency)}</Text>
                      <Pressable onPress={() => remove(line.id)} disabled={busy} hitSlop={8}>
                        <Text style={styles.link}>{t("cart.remove")}</Text>
                      </Pressable>
                    </View>
                  </View>
                );
              })}

              <View style={styles.subtotals}>
                {group.subtotals.map((s) => (
                  <View key={s.currency} style={styles.totalRow}>
                    <Text style={styles.totalLabel}>{t("cart.subtotal")}</Text>
                    <Text style={styles.totalValue}>{money(s.amount, s.currency)}</Text>
                  </View>
                ))}
                {/* One creator, two currencies is refused server-side
                    (cart_mixed_currencies): an order carries one escrow and an
                    escrow carries one currency. Said here rather than
                    discovered as a 400 after the button. */}
                {group.subtotals.length > 1 ? <Hint>{t("cart.mixedCurrency")}</Hint> : null}
                {!selected ? <Hint>{t("cart.groupExcluded")}</Hint> : null}
              </View>
            </View>
          );
        })}
      </View>

      <View style={{ height: space(4) }} />
      <Card>
        <SectionTitle>
          {selectedGroups.length === groups.length ? t("cart.total") : t("cart.totalSelected")}
        </SectionTitle>
        {selectedTotals.length === 0 ? (
          <Hint>{t("cart.noneSelected")}</Hint>
        ) : (
          selectedTotals.map((s) => (
            <View key={s.currency} style={styles.totalRow}>
              <Text style={styles.grandLabel}>{s.currency}</Text>
              <Text style={styles.grandValue}>{money(s.amount, s.currency)}</Text>
            </View>
          ))
        )}
        {/* Why there is no single figure. A buyer who can see two totals and
            no grand total will otherwise assume the screen forgot to add
            them up. */}
        {selectedTotals.length > 1 ? <Hint>{t("cart.totalsNote")}</Hint> : null}
        <Hint>{t("cart.rule")}</Hint>
        {groups.length > 1 ? <Hint>{t("cart.selectionNote")}</Hint> : null}
        <View style={{ height: space(3) }} />
        <PrimaryButton
          title={
            busy
              ? t("common.working")
              : selectedGroups.length === groups.length
                ? t("cart.checkout")
                : t("cart.checkoutSelected", { n: selectedGroups.length })
          }
          onPress={checkout}
          loading={busy}
          disabled={selectedGroups.length === 0}
        />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  link: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.indigo },
  receiptRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space(3),
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingTop: space(2.5),
    marginTop: space(2.5),
  },
  receiptName: { flex: 1, fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink },
  selectRow: { flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: space(3) },
  selectCount: { fontSize: font.tiny, fontFamily: family.body, color: colors.muted },
  group: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
  },
  groupExcluded: { opacity: 0.6 },
  groupHead: { flexDirection: "row", alignItems: "center", gap: space(2), paddingVertical: space(1) },
  groupName: { flex: 1, fontSize: font.body, fontFamily: family.bodyBold, color: colors.ink },
  line: {
    flexDirection: "row",
    gap: space(3),
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingTop: space(2.5),
    marginTop: space(2.5),
  },
  lineRejected: { borderLeftWidth: 3, borderLeftColor: colors.danger, paddingLeft: space(2) },
  lineMain: { flex: 1, minWidth: 0 },
  lineLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink },
  lineMeta: { fontSize: font.tiny, fontFamily: family.body, color: colors.muted, marginTop: 2 },
  lineNote: { fontSize: font.tiny, fontFamily: family.body, color: colors.muted, marginTop: space(1) },
  lineRejectedText: {
    fontSize: font.tiny,
    fontFamily: family.bodySemi,
    color: colors.danger,
    marginTop: space(1),
  },
  /* A fixed side column rather than a shrinking one: the amount is the thing
     that must never wrap or clip, and at 360 dp "1 250 000 XOF" is the widest
     it gets. */
  lineSide: { alignItems: "flex-end", minWidth: 96 },
  lineAmount: { fontSize: font.small, fontFamily: family.bodyBold, color: colors.ink },
  subtotals: { borderTopWidth: 1, borderTopColor: colors.line, marginTop: space(2.5), paddingTop: space(2) },
  totalRow: { flexDirection: "row", justifyContent: "space-between", gap: space(3), paddingVertical: 2 },
  totalLabel: { fontSize: font.tiny, fontFamily: family.body, color: colors.muted },
  totalValue: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink },
  grandLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.muted },
  grandValue: { fontSize: font.body, fontFamily: family.display, color: colors.ink },
});
