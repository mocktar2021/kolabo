import { useCallback, useEffect, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api, mediaSrc } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { isBusinessLike, useAuth } from "../lib/auth";
import { useCart } from "../lib/cart";
import type { CreatorSnapshot } from "../lib/cartTotals";
import { PLATFORM_LABELS, deliverableLabel, deliverablesFor } from "../lib/platforms";
import { MIN_PACKAGE_PRICE, minPrice } from "../lib/pricing";
import type { DirectOrder, PublicProfileData } from "../lib/discoveryTypes";
import type { Package, SocialAccount } from "../lib/profileTypes";
import { followerNote, socialStatusChip } from "../lib/socialStatus";
import {
  Banner,
  Card,
  Field,
  GhostButton,
  Hint,
  PrimaryButton,
  Screen,
  SectionTitle,
  Select,
  Title,
} from "../components/ui";
import { colors, family, font, radius, space } from "../theme";
/* Side-effect import: registers the cart.* and public.negotiate* copy on the
   i18n instance. Without it the two new controls below render raw keys. */
import "../lib/cartStrings";
/* Side-effect import: the audience block below reads profile.socialStatus*,
   profile.socialFollowers* and profile.socialAudienceTitle, registered on
   i18n by lib/socialConnectStrings. Without this line a brand reads raw keys
   on the one page that most needs to be readable. */
import "../lib/socialConnectStrings";
import type { AppScreenProps } from "../navigation/types";

/* A creator's storefront, seen by a buyer. Mirrors the web PublicProfile's
   immediate-order path against the same endpoints: the profile is public
   (GET /profiles/influencer/{id}/public), and ordering a package is
   POST /campaigns/orders with {package_id, note}. Nothing is charged at
   order time — the creator has 48 h to accept, and escrow is funded only
   after the contract is signed. That rule is printed next to the button,
   because it is the fact that makes the button safe to press.

   THREE WAYS OUT OF THIS SCREEN NOW, and the fast one is deliberately
   untouched:

     ORDER     the pack as listed, straight away. One pack from one creator
               should not have to go through a basket to be bought, and making
               it would put a screen in the middle of the shortest journey in
               the app.
     ADD       the same pack, put aside instead. This is for the other case —
               four packs from three people, decided across four profiles and
               paid for once. Nothing is sent: the basket is the client's
               until checkout (lib/cart.tsx), and the price stored on the line
               is only what to show, because the order is priced off the live
               pack row at checkout.
     PROPOSE   the buyer's own terms, sent as the custom form of the same
               orders endpoint, or added to the basket like any other line.
               Secondary on purpose — the published price is still the fast
               path — and it is the way out for the deals that do not fit one,
               which are the deals that were being agreed on WhatsApp.

   NONE OF THE TERMS ARE VALIDATED HERE beyond "the boxes are filled". The
   floor price, the quantity range, the timeline range and the
   platform/deliverable pair are all campaigns/negotiated.py's, and its
   refusals arrive with codes lib/errorMessages already says in both
   languages. Restating any of it here would be a second copy of those rules,
   and the copy is the one that drifts. The floor is the one exception and
   only as a HINT, interpolated from lib/pricing.ts — a number to aim at
   before typing beats a 400 afterwards. */

/* Mirrors CURRENCIES on the campaign form, read off the floor table rather
   than typed again so a currency added to pricing.ts is offerable here the
   same day. */
const CURRENCIES = Object.keys(MIN_PACKAGE_PRICE);

/* Quantities a custom offer can be built from. The API allows up to 100
   (campaigns.negotiated.MAX_OFFER_QUANTITY) and this stops at 20 for the
   reason web's does: past twenty deliverables the buyer is writing a brief,
   which is the other product and better suited to it. */
const QUANTITY_OPTIONS = Array.from({ length: 20 }, (_, i) => String(i + 1));

function PackageRow({ p, selected, onSelect }: {
  p: Package;
  selected: boolean;
  onSelect: () => void;
}) {
  const { i18n } = useTranslation();
  return (
    <Pressable onPress={onSelect} style={[styles.pkg, selected && styles.pkgSelected]}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space(2) }}>
        <Text style={[styles.pkgTitle, selected && { color: colors.teal600 }]} numberOfLines={2}>
          {p.title}
        </Text>
        <Text style={styles.pkgPrice}>
          {p.price_amount.toLocaleString(i18n.language)} {p.currency}
        </Text>
      </View>
      <Text style={styles.pkgSub}>
        {PLATFORM_LABELS[p.platform] ?? p.platform} · {deliverableLabel(p.deliverable_type)}
        {p.quantity > 1 ? ` · ×${p.quantity}` : ""}
      </Text>
    </Pressable>
  );
}

/* One connected account, as the buyer reads it: which platform, which handle,
   how big the audience is, WHERE THAT SIZE CAME FROM, and what state the
   account itself is in.

   THIS SCREEN USED TO RENDER NONE OF IT. social_accounts was fetched and read
   only to work out which platforms could be ordered and whom to name on a
   basket line, so a follower number read back through the creator's own OAuth
   token and a number somebody typed into a form reached the buyer as the same
   thing, which is to say as nothing at all. The provenance line is the reason
   this component exists; the chip beside it is the second half of the same
   sentence, because a number's source and a handle's state are two different
   questions and one badge cannot answer both.

   EVERY ACCOUNT IS LISTED, whatever its state, which is the rule
   get_public_profile already applies server side: it selects every row and
   lets the client say what each one is. A brand is better served by seeing an
   unproven handle labelled as one than by not seeing it. */
function SocialRow({ a }: { a: SocialAccount }) {
  const { t, i18n } = useTranslation();
  const label = PLATFORM_LABELS[a.platform] ?? a.platform;
  const chip = socialStatusChip(a.status);
  const note = followerNote(a, i18n.language);
  const tone = {
    strong: styles.chipStrong,
    quiet: styles.chipQuiet,
    neutral: styles.chipMuted,
    bad: styles.chipBad,
  }[chip.tone];
  return (
    <View style={styles.social}>
      <View style={{ flexShrink: 1 }}>
        <Text style={styles.socialTitle}>
          {label} · @{a.handle}
        </Text>
        {a.follower_count !== null && a.follower_count !== undefined ? (
          <Text style={styles.socialCount}>
            {a.follower_count.toLocaleString(i18n.language)} {t("public.audienceUnit")}
          </Text>
        ) : null}
        {note ? (
          <Text style={[styles.socialSource, note.checked ? styles.socialSourceChecked : null]}>
            {t(note.key, { platform: label, date: note.date })}
          </Text>
        ) : null}
      </View>
      <Text style={[styles.chip, tone]}>{t(chip.key)}</Text>
    </View>
  );
}

export default function CreatorPublicScreen({ navigation, route }: AppScreenProps<"CreatorPublic">) {
  const { userId } = route.params;
  const { t, i18n } = useTranslation();
  const { token, role, userId: viewerId } = useAuth();
  const { add: addToCart, count: cartCount } = useCart();

  const [profile, setProfile] = useState<PublicProfileData | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [ordered, setOrdered] = useState<DirectOrder | null>(null);
  /* The one line of feedback adding to the basket produces. Nothing was sent
     to the server, so it is not a receipt and does not read like one. */
  const [cartMessage, setCartMessage] = useState<string | null>(null);

  /* The custom-terms panel. Mutually exclusive with the confirm panel, which
     is why note, busy and orderError are shared rather than duplicated: only
     one of the two can be open, and a buyer who typed a note into one and
     switched should not have to type it again. Only the terms live in their
     own state, because only the terms are new — everything downstream (the
     48 h window, the counter-offers in components/invitations/Negotiation,
     the contract, escrow) is the same object a pack order produces. */
  const [negotiating, setNegotiating] = useState(false);
  const [negPlatform, setNegPlatform] = useState("");
  const [negDeliverable, setNegDeliverable] = useState("");
  const [negQuantity, setNegQuantity] = useState(1);
  const [negRate, setNegRate] = useState("");
  const [negCurrency, setNegCurrency] = useState(CURRENCIES[0] ?? "XOF");
  const [negDays, setNegDays] = useState("");

  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    try {
      const p = await api<PublicProfileData>(
        `/profiles/influencer/${userId}/public?language=${i18n.language}`
      );
      setProfile(p);
      setSelectedId((prev) => prev ?? p.packages.find((x) => x.is_active)?.id ?? null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setNotFound(true);
      else setError(errorText(e, t));
    }
  }, [userId, i18n.language, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const packages = profile?.packages.filter((p) => p.is_active) ?? [];
  const selectedPackage = packages.find((p) => p.id === selectedId) ?? packages[0] ?? null;

  /* What this creator can actually be asked for. Their published packs first,
     then every connected account: somebody with a TikTok account and no TikTok
     pack still sells TikTok, they simply never listed a bundle for it, and
     refusing to offer it would send that deal off-platform for no reason.
     Filtered against the shared catalog so the two pickers can never build a
     pair the API answers 400 to. */
  const sellablePlatforms = [
    ...new Set([
      ...packages.map((p) => p.platform),
      ...(profile?.social_accounts ?? []).map((a) => a.platform),
    ]),
  ].filter((id) => deliverablesFor(id).length > 0);

  /* Only the buying side may order — the same rule the API applies (403 to an
     influencer) — and nobody orders from themselves. It gates the basket too:
     the same rule, one step earlier than the server's. */
  const canOrder = isBusinessLike(role) && viewerId !== userId;
  const canBuy = canOrder && (selectedPackage !== null || sellablePlatforms.length > 0);

  /* How this creator has to be named on a basket line.

     The cart groups by creator and has no way to look anybody up: no endpoint
     answers "who is this user id", and there should not be one — that is an
     enumeration API over everybody on the platform, handed to whoever holds
     any token. So the four identity fields are captured here, on the one
     screen that already has them on display, exactly as web does it.

     top_platform is the single biggest connected account and never a sum
     across them: somebody following on two networks would otherwise be counted
     twice. Same rule app/core/identity.py applies server-side. */
  function cartIdentity(p: PublicProfileData): CreatorSnapshot {
    const top = [...p.social_accounts]
      .filter((a) => a.follower_count !== null)
      .sort((a, b) => (b.follower_count ?? 0) - (a.follower_count ?? 0))[0];
    return {
      display_name: p.display_name,
      avatar_url: p.avatar_url,
      top_platform: top ? top.platform : null,
      top_follower_count: top ? top.follower_count : null,
    };
  }

  async function sendOrder() {
    if (!selectedPackage) return;
    setBusy(true);
    setOrderError(null);
    try {
      const trimmed = note.trim();
      const res = await api<DirectOrder>("/campaigns/orders", {
        method: "POST",
        token,
        body: { package_id: selectedPackage.id, note: trimmed || null },
      });
      setOrdered(res);
      setConfirming(false);
    } catch (e) {
      setOrderError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  /* The buyer's own terms, sent as the custom form of the same endpoint. What
     comes back is the same order a pack produces — same 48 h clock, same
     accept path, same contract — so the success state below is shared rather
     than written twice. */
  async function sendNegotiatedOrder() {
    if (!profile) return;
    setBusy(true);
    setOrderError(null);
    try {
      const trimmed = note.trim();
      const res = await api<DirectOrder>("/campaigns/orders", {
        method: "POST",
        token,
        body: {
          creator_user_id: profile.user_id,
          platform: negPlatform,
          deliverable_type: negDeliverable,
          quantity: negQuantity,
          rate_amount: Number(negRate),
          currency: negCurrency,
          timeline_days: Number(negDays),
          ...(trimmed ? { note: trimmed } : {}),
        },
      });
      setOrdered(res);
      setNegotiating(false);
    } catch (e) {
      setOrderError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  function addPackageToCart() {
    if (!profile || !selectedPackage) return;
    const trimmed = note.trim();
    const added = addToCart({
      creator_user_id: profile.user_id,
      creator: cartIdentity(profile),
      note: trimmed || null,
      label: selectedPackage.title,
      package_id: selectedPackage.id,
      platform: selectedPackage.platform,
      deliverable_type: selectedPackage.deliverable_type,
      quantity: selectedPackage.quantity ?? 1,
      /* A pack carries the creator's own timeline; the buyer never names one,
         so there is nothing to put here. */
      timeline_days: null,
      amount: selectedPackage.price_amount,
      currency: selectedPackage.currency,
    });
    setCartMessage(added ? t("cart.added") : t("cart.full"));
  }

  function addNegotiatedToCart() {
    if (!profile) return;
    const trimmed = note.trim();
    const added = addToCart({
      creator_user_id: profile.user_id,
      creator: cartIdentity(profile),
      note: trimmed || null,
      label: deliverableLabel(negDeliverable),
      package_id: null,
      platform: negPlatform,
      deliverable_type: negDeliverable,
      quantity: negQuantity,
      timeline_days: Number(negDays),
      amount: Number(negRate),
      currency: negCurrency,
    });
    if (added) {
      setNegotiating(false);
      setNote("");
    }
    setCartMessage(added ? t("cart.added") : t("cart.full"));
  }

  /* Opened seeded from the pack on screen rather than blank: the buyer got
     here by looking at that offer, and the thing they want to change is
     usually one field of it. */
  function openNegotiate() {
    const platform = selectedPackage?.platform ?? sellablePlatforms[0] ?? "";
    setNegPlatform(platform);
    setNegDeliverable(
      selectedPackage && selectedPackage.platform === platform
        ? selectedPackage.deliverable_type
        : deliverablesFor(platform)[0] ?? ""
    );
    setNegQuantity(1);
    setNegRate("");
    setNegCurrency(selectedPackage?.currency ?? CURRENCIES[0] ?? "XOF");
    setNegDays("");
    setOrderError(null);
    setCartMessage(null);
    setNegotiating(true);
  }

  /* The deliverable list is per-platform, so a platform change has to reset
     it. Left alone, "Reel" would survive a switch to LinkedIn and the offer
     would be refused for a pair the form itself built. */
  function changeNegPlatform(platform: string) {
    setNegPlatform(platform);
    setNegDeliverable(deliverablesFor(platform)[0] ?? "");
  }

  const negComplete = !!negPlatform && !!negDeliverable && !!negRate && !!negDays;

  if (notFound) {
    return (
      <Screen>
        <Banner kind="error">{t("public.notFound")}</Banner>
      </Screen>
    );
  }

  const avatar = mediaSrc(profile?.avatar_url);

  return (
    <Screen
      loading={profile === null && !error && !notFound}
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
      {profile === null ? null : (
        <>
          <View style={styles.head}>
            {avatar ? (
              <Image source={{ uri: avatar }} style={styles.avatar} />
            ) : (
              <View style={[styles.avatar, styles.avatarEmpty]}>
                <Text style={styles.avatarLetter}>
                  {(profile.display_name || "?").charAt(0).toUpperCase()}
                </Text>
              </View>
            )}
            <View style={{ flex: 1 }}>
              <Title>{profile.display_name || t("discover.creator")}</Title>
              {profile.headline ? <Text style={styles.headline}>{profile.headline}</Text> : null}
              {profile.follower_count !== null ? (
                <Text style={styles.audience}>
                  {profile.follower_count.toLocaleString(i18n.language)} {t("public.audienceUnit")}
                </Text>
              ) : null}
            </View>
          </View>

          {profile.categories.length > 0 ? (
            <Text style={styles.cats}>
              {profile.categories.map((c) => t(`cat.${c}`, { defaultValue: c })).join(" · ")}
            </Text>
          ) : null}

          {profile.bio ? <Text style={styles.bio}>{profile.bio}</Text> : null}

          {/* ABOVE THE PACKAGES, because the audience is what the price is
              being judged against, and a buyer who has already picked a pack
              has stopped reading. */}
          {profile.social_accounts.length > 0 ? (
            <>
              <SectionTitle>{t("profile.socialAudienceTitle")}</SectionTitle>
              <View style={{ gap: space(2), marginBottom: space(2) }}>
                {profile.social_accounts.map((a) => (
                  <SocialRow key={a.id} a={a} />
                ))}
              </View>
            </>
          ) : null}

          <SectionTitle>{t("public.packages")}</SectionTitle>
          {packages.length === 0 ? (
            <Hint>{t("public.noPackages")}</Hint>
          ) : (
            <View style={{ gap: space(2) }}>
              {packages.map((p) => (
                <PackageRow
                  key={p.id}
                  p={p}
                  selected={selectedPackage?.id === p.id}
                  onSelect={() => setSelectedId(p.id)}
                />
              ))}
            </View>
          )}

          {canBuy ? (
            <View style={{ marginTop: space(4), gap: space(3) }}>
              {ordered ? (
                <Card>
                  <Banner kind="success">{t("public.orderSent")}</Banner>
                  <GhostButton
                    title={t("public.orderView")}
                    onPress={() => navigation.navigate("Campaigns")}
                  />
                </Card>
              ) : confirming && selectedPackage ? (
                <Card>
                  <SectionTitle>{t("public.orderConfirm")}</SectionTitle>
                  <Text style={styles.confirmLine}>
                    {selectedPackage.title} · {selectedPackage.price_amount.toLocaleString(i18n.language)}{" "}
                    {selectedPackage.currency}
                  </Text>
                  {orderError ? <Banner kind="error">{orderError}</Banner> : null}
                  <Field
                    label={t("public.orderNote")}
                    value={note}
                    onChangeText={setNote}
                    multiline
                    numberOfLines={3}
                  />
                  <Hint>{t("public.orderRule")}</Hint>
                  <View style={{ height: space(3) }} />
                  <PrimaryButton
                    title={busy ? t("common.working") : t("public.orderSend")}
                    onPress={sendOrder}
                    loading={busy}
                  />
                  <View style={{ height: space(2) }} />
                  <GhostButton title={t("public.orderCancel")} onPress={() => setConfirming(false)} />
                </Card>
              ) : negotiating ? (
                <Card>
                  <SectionTitle>{t("public.negotiateTitle")}</SectionTitle>
                  {orderError ? <Banner kind="error">{orderError}</Banner> : null}

                  <Select
                    label={t("public.negotiatePlatform")}
                    value={negPlatform}
                    options={sellablePlatforms.map((p) => ({
                      value: p,
                      label: PLATFORM_LABELS[p] ?? p,
                    }))}
                    onChange={changeNegPlatform}
                  />
                  <Select
                    label={t("public.negotiateDeliverable")}
                    value={negDeliverable}
                    options={deliverablesFor(negPlatform).map((d) => ({
                      value: d,
                      label: deliverableLabel(d),
                    }))}
                    onChange={setNegDeliverable}
                  />
                  <Select
                    label={t("public.negotiateQuantity")}
                    value={String(negQuantity)}
                    options={QUANTITY_OPTIONS.map((n) => ({ value: n, label: n }))}
                    onChange={(v) => setNegQuantity(Number(v))}
                  />
                  {/* Price and currency side by side: they are one answer, and
                      stacking them at 360 dp puts the unit a scroll away from
                      the number it belongs to. */}
                  <View style={{ flexDirection: "row", gap: space(3) }}>
                    <View style={{ flex: 3 }}>
                      <Field
                        label={t("public.negotiatePrice")}
                        value={negRate}
                        onChangeText={(v) => setNegRate(v.replace(/\D/g, ""))}
                        keyboardType="number-pad"
                        placeholder="40000"
                      />
                    </View>
                    <View style={{ flex: 2 }}>
                      <Select
                        label={t("campaign.currency")}
                        value={negCurrency}
                        options={CURRENCIES.map((c) => ({ value: c, label: c }))}
                        onChange={setNegCurrency}
                      />
                    </View>
                  </View>
                  {/* The same floor the pack form states, from the same table
                      (lib/pricing.ts mirrors backend/app/core/pricing.py). A
                      negotiated price cannot undercut it either — that is the
                      point of having one. */}
                  <Hint>
                    {t("public.negotiateFloor", {
                      n: minPrice(negCurrency).toLocaleString(i18n.language),
                      currency: negCurrency,
                    })}
                  </Hint>
                  <View style={{ height: space(3) }} />
                  <Field
                    label={t("public.negotiateDays")}
                    value={negDays}
                    onChangeText={(v) => setNegDays(v.replace(/\D/g, ""))}
                    keyboardType="number-pad"
                    placeholder="7"
                  />
                  <Field
                    label={t("public.orderNote")}
                    value={note}
                    onChangeText={setNote}
                    multiline
                    numberOfLines={3}
                  />
                  <Hint>{t("public.orderRule")}</Hint>
                  <View style={{ height: space(3) }} />
                  <PrimaryButton
                    title={busy ? t("common.working") : t("public.negotiateSend")}
                    onPress={sendNegotiatedOrder}
                    loading={busy}
                    disabled={!negComplete}
                  />
                  <View style={{ height: space(2) }} />
                  {/* The custom offer put aside instead of sent. A brand
                      assembling one basket across several profiles needs this
                      as much as it needs it for a listed pack — and a bespoke
                      offer is exactly the line most likely to be one of
                      four. */}
                  <GhostButton
                    title={t("cart.add")}
                    onPress={addNegotiatedToCart}
                    disabled={busy || !negComplete}
                  />
                  <View style={{ height: space(2) }} />
                  <GhostButton
                    title={t("public.orderCancel")}
                    onPress={() => {
                      setNegotiating(false);
                      setOrderError(null);
                    }}
                  />
                </Card>
              ) : (
                <View style={{ gap: space(2) }}>
                  {selectedPackage ? (
                    <>
                      <PrimaryButton title={t("public.order")} onPress={() => setConfirming(true)} />
                      {/* Beside the order button, not instead of it. */}
                      <GhostButton title={t("cart.add")} onPress={addPackageToCart} />
                      <View style={styles.orRow}>
                        <View style={styles.orLine} />
                        <Text style={styles.orText}>{t("public.negotiateOr")}</Text>
                        <View style={styles.orLine} />
                      </View>
                    </>
                  ) : null}
                  {sellablePlatforms.length > 0 ? (
                    <GhostButton title={t("public.negotiate")} onPress={openNegotiate} />
                  ) : null}
                </View>
              )}

              {/* Shared by both add-to-cart buttons: one line saying it worked,
                  and the way to the basket. */}
              {cartMessage ? (
                <Card>
                  <Banner kind="success">{cartMessage}</Banner>
                  <GhostButton
                    title={t("cart.view", { n: cartCount })}
                    onPress={() => navigation.navigate("Cart")}
                  />
                </Card>
              ) : null}
            </View>
          ) : null}

          <SectionTitle>{t("public.howItWorks")}</SectionTitle>
          <View style={{ gap: space(1) }}>
            <Hint>{t("public.how1")}</Hint>
            <Hint>{t("public.how2")}</Hint>
            <Hint>{t("public.how3")}</Hint>
          </View>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: "row", gap: space(3), alignItems: "center", marginBottom: space(2) },
  avatar: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.surface2 },
  avatarEmpty: { alignItems: "center", justifyContent: "center" },
  avatarLetter: { fontSize: font.h1, fontFamily: family.display, color: colors.muted },
  headline: { fontFamily: family.body, fontSize: font.small, color: colors.muted, marginTop: -space(1) },
  audience: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginTop: space(1) },
  cats: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginBottom: space(2) },
  bio: { fontFamily: family.body, fontSize: font.small, color: colors.ink, marginBottom: space(2) },
  social: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
    gap: space(2),
  },
  socialTitle: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink },
  socialCount: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 2 },
  socialSource: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 2, lineHeight: 16 },
  /* Only the checked figure is coloured. A positive marker that looks like
     the muted line above it is not a marker. */
  socialSourceChecked: { fontFamily: family.bodySemi, color: colors.success },
  chip: {
    fontSize: font.tiny,
    fontFamily: family.bodySemi,
    overflow: "hidden",
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: 3,
  },
  /* The same four tones SocialsSection paints, so the creator and the brand
     are looking at one visual language for one set of states. */
  chipStrong: { backgroundColor: "#e7f6f0", color: colors.success },
  chipQuiet: { backgroundColor: colors.surface, color: colors.indigo },
  chipMuted: { backgroundColor: colors.surface2, color: colors.muted },
  chipBad: { backgroundColor: "#fbeaea", color: colors.danger },
  pkg: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    padding: space(3),
  },
  pkgSelected: { borderColor: colors.teal, backgroundColor: colors.tealSoft },
  pkgTitle: { fontSize: font.body, fontFamily: family.bodyBold, color: colors.ink, flexShrink: 1 },
  pkgPrice: { fontSize: font.body, fontFamily: family.bodyBold, color: colors.ink },
  pkgSub: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 3 },
  confirmLine: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(3) },
  orRow: { flexDirection: "row", alignItems: "center", gap: space(2), marginTop: space(1) },
  orLine: { flex: 1, height: 1, backgroundColor: colors.line },
  orText: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted },
});
