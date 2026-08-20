import { useMemo, type ReactNode } from "react";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";
import { Ionicons } from "@expo/vector-icons";
import { colors, family, font, radius, shadow, space } from "../theme";
/* Side-effect import: the landing.* keys are registered on i18n at runtime
   (see lib/landingStrings.ts). Splash reads two of them, so this file must
   pull the bundle in itself rather than relying on the screen to have done
   it — RootNavigator renders Splash without going near LandingScreen. */
import "../lib/landingStrings";

/* The pre-auth brand furniture: the splash, and the illustrative product
   cards that sit in the top panel of each carousel slide.

   THE CARDS ARE DRAWINGS OF REAL SURFACES, not live data and not components
   reused from the signed-in app. Same choice web/src/pages/Landing.tsx makes
   for its workflow vignettes and for the same reasons: no request to make on
   a screen that renders before there is a token, no empty state to design for
   the morning the pilot roster is thin, and nothing here can drift when the
   real screen changes. The tradeoff is that they can go stale — if the
   creator card grows a field, this drawing will not.

   They are hidden from screen readers, exactly as web marks its vignettes
   aria-hidden. What a slide actually promises is in the headline and the body
   beneath the panel, and those are the sentences that have to be true; a
   reader who cannot see the picture should hear the promise once, not hear an
   invented person's follower count read out as if it were a fact. */

/* The mint-to-lavender field behind each card, and the teal-to-blue of the
   app tile and the avatars. Both ends of both ramps are existing theme
   tokens — nothing new is invented here, they are only put in one place so a
   ramp is stated once rather than per component. */
const PANEL_FROM = colors.tealSoft;
const PANEL_TO = colors.surface2;
const TILE_FROM = colors.teal;
const TILE_TO = colors.indigo600;
/* Splash type on the navy field. An alpha rather than a token because the
   colour it needs to be is "the background, lightened" — a flat grey here
   reads as a different ink rather than as quieter type. */
const SPLASH_PALE = "rgba(255, 255, 255, 0.66)";

/* HOW THE GRADIENTS ARE DRAWN, and why it is not expo-linear-gradient.

   That package would be one more dependency and one more native module for a
   decorative ramp on a single screen, and this app has kept its dependency
   list short on purpose. A two-stop linear gradient is a stack of flex:1
   bands with the colour interpolated between the ends: at 24 bands across a
   300 dp panel each band is under 13 dp, and the two ends here are near-white
   neighbours, so there is nothing to see a seam in. Vertical only, which is
   what every gradient in this design happens to be.

   Both stops must be six-digit hex — every colour in theme.ts is. */
const GRADIENT_BANDS = 24;

function channels(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function mix(from: string, to: string, t: number): string {
  const a = channels(from);
  const b = channels(to);
  const at = (i: 0 | 1 | 2) => Math.round(a[i] + (b[i] - a[i]) * t);
  return `rgb(${at(0)}, ${at(1)}, ${at(2)})`;
}

export function Gradient({
  from,
  to,
  bands = GRADIENT_BANDS,
  style,
  children,
}: {
  from: string;
  to: string;
  bands?: number;
  style?: StyleProp<ViewStyle>;
  children?: ReactNode;
}) {
  const steps = useMemo(
    () => Array.from({ length: bands }, (_, i) => mix(from, to, bands < 2 ? 0 : i / (bands - 1))),
    [from, to, bands]
  );
  return (
    /* overflow first so a borderRadius passed in `style` clips the bands. */
    <View style={[styles.clip, style]}>
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        {steps.map((c, i) => (
          <View key={i} style={{ flex: 1, backgroundColor: c }} />
        ))}
      </View>
      {children}
    </View>
  );
}

/* The app tile: rounded square, teal to blue, white K. */
export function BrandMark({ size = 76 }: { size?: number }) {
  return (
    <Gradient
      from={TILE_FROM}
      to={TILE_TO}
      bands={14}
      style={{
        width: size,
        height: size,
        borderRadius: Math.round(size * 0.28),
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Text style={{ fontFamily: family.display, fontSize: Math.round(size * 0.46), color: colors.white }}>
        K
      </Text>
    </Gradient>
  );
}

function Avatar({ size, initials, fontSize }: { size: number; initials: string; fontSize: number }) {
  return (
    <Gradient
      from={TILE_FROM}
      to={TILE_TO}
      bands={10}
      style={{ width: size, height: size, borderRadius: size / 2, alignItems: "center", justifyContent: "center" }}
    >
      <Text style={{ fontFamily: family.bodyBold, fontSize, color: colors.white }}>{initials}</Text>
    </Gradient>
  );
}

/* The cold-start screen, and the root's loading state: navy field, app tile,
   wordmark, and the product in two lines at the foot. It stands in for the
   bare ActivityIndicator RootNavigator used to show while the keystore was
   being read. */
export function Splash() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  return (
    <View style={styles.splash}>
      <View style={styles.splashCentre}>
        <BrandMark />
        <Text style={styles.wordmark}>Kolabo</Text>
      </View>
      <View style={[styles.splashFoot, { paddingBottom: insets.bottom + space(8) }]}>
        <Text style={styles.splashTagline}>{t("landing.taglineA")}</Text>
        <Text style={styles.splashTagline}>{t("landing.taglineB")}</Text>
      </View>
    </View>
  );
}

function CreatorCardArt() {
  const { t } = useTranslation();
  const chips = [t("landing.s1Chip1"), t("landing.s1Chip2"), t("landing.s1Chip3")];
  return (
    <>
      <View style={styles.row}>
        <Avatar size={44} initials="TH" fontSize={15} />
        <View style={styles.rowBody}>
          <View style={styles.nameRow}>
            <Text style={styles.name} numberOfLines={1}>
              Tatiana Haina
            </Text>
            <View style={styles.chipTeal}>
              <Ionicons name="checkmark" size={10} color={colors.teal600} />
              <Text style={styles.chipTealText}>{t("landing.s1Verified")}</Text>
            </View>
          </View>
          <Text style={styles.meta} numberOfLines={1}>
            {t("landing.s1Meta")}
          </Text>
        </View>
      </View>
      <View style={styles.chipRow}>
        {chips.map((c) => (
          <View key={c} style={styles.chipPale}>
            <Text style={styles.chipPaleText}>{c}</Text>
          </View>
        ))}
      </View>
      <View style={styles.cardFoot}>
        <Text style={styles.price}>10 000 XOF</Text>
        <View style={styles.cardBtn}>
          <Text style={styles.cardBtnText}>{t("landing.s1CardCta")}</Text>
        </View>
      </View>
    </>
  );
}

function Tick({ done }: { done: boolean }) {
  return done ? (
    <View style={styles.tickOn}>
      <Ionicons name="checkmark" size={11} color={colors.white} />
    </View>
  ) : (
    <View style={styles.tickOff} />
  );
}

function EscrowCardArt() {
  const { t } = useTranslation();
  const steps = [
    { label: t("landing.s2Step1"), done: true },
    { label: t("landing.s2Step2"), done: true },
    { label: t("landing.s2Step3"), done: false },
  ];
  return (
    <>
      <View style={styles.headRow}>
        <Text style={styles.cardTitle} numberOfLines={1}>
          {t("landing.s2CardTitle")}
        </Text>
        <View style={styles.chipTeal}>
          <Ionicons name="lock-closed" size={10} color={colors.teal600} />
          <Text style={styles.chipTealText}>{t("landing.s2CardChip")}</Text>
        </View>
      </View>
      <Text style={styles.amount}>10 000 XOF</Text>
      <Text style={styles.meta}>{t("landing.s2CardSub")}</Text>
      <View style={styles.divider} />
      {steps.map((s) => (
        <View key={s.label} style={styles.stepRow}>
          <Tick done={s.done} />
          <Text style={[styles.stepLabel, !s.done && styles.stepLabelPending]} numberOfLines={1}>
            {s.label}
          </Text>
        </View>
      ))}
    </>
  );
}

function ReviewCardArt() {
  const { t } = useTranslation();
  const chips = [t("landing.s3Chip1"), t("landing.s3Chip2"), t("landing.s3Chip3")];
  return (
    <>
      <View style={styles.headRow}>
        <View style={styles.starRow}>
          {[0, 1, 2, 3, 4].map((i) => (
            <Ionicons key={i} name="star" size={12} color={colors.teal} />
          ))}
          <Text style={styles.rating}>{t("landing.s3Rating")}</Text>
        </View>
        <View style={styles.chipTeal}>
          <Ionicons name="checkmark" size={10} color={colors.teal600} />
          <Text style={styles.chipTealText}>{t("landing.s3CardChip")}</Text>
        </View>
      </View>
      <Text style={styles.quote}>{t("landing.s3Quote")}</Text>
      <View style={styles.whoRow}>
        <Avatar size={26} initials="A" fontSize={11} />
        <View style={styles.rowBody}>
          <Text style={styles.who} numberOfLines={1}>
            {t("landing.s3Who")}
          </Text>
          <Text style={styles.metaTiny} numberOfLines={1}>
            {t("landing.s3When")}
          </Text>
        </View>
      </View>
      <View style={styles.divider} />
      <View style={[styles.chipRow, styles.chipRowTight]}>
        {chips.map((c) => (
          <View key={c} style={styles.chipPale}>
            <Text style={styles.chipPaleText}>{c}</Text>
          </View>
        ))}
      </View>
    </>
  );
}

/* The top panel of a slide: the mint-to-lavender field with one card on it.

   `height` and `topInset` are decided by the screen, which is the only place
   that knows how tall this handset is and how much of the top belongs to the
   status bar. The panel bleeds under the status bar deliberately — a white
   strip above a coloured field reads as a rendering fault — and `topInset` is
   padding rather than a smaller height, so the card still centres in the part
   of the panel that is actually visible. */
export function SlideArt({
  index,
  height,
  topInset = 0,
}: {
  index: number;
  height: number;
  topInset?: number;
}) {
  return (
    <Gradient from={PANEL_FROM} to={PANEL_TO} style={[styles.panel, { height, paddingTop: topInset }]}>
      <View
        style={styles.card}
        accessible={false}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        {index === 0 ? <CreatorCardArt /> : index === 1 ? <EscrowCardArt /> : <ReviewCardArt />}
      </View>
    </Gradient>
  );
}

const styles = StyleSheet.create({
  clip: { overflow: "hidden" },

  splash: { flex: 1, backgroundColor: colors.indigo },
  splashCentre: { flex: 1, alignItems: "center", justifyContent: "center" },
  wordmark: {
    fontFamily: family.display,
    fontSize: 30,
    color: colors.white,
    letterSpacing: -0.4,
    marginTop: space(4),
  },
  splashFoot: { alignItems: "center", paddingHorizontal: space(6) },
  splashTagline: {
    fontFamily: family.body,
    fontSize: font.tiny,
    color: SPLASH_PALE,
    lineHeight: 18,
    textAlign: "center",
  },

  panel: { width: "100%", alignItems: "center", justifyContent: "center", paddingHorizontal: space(7) },
  card: {
    width: "100%",
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    padding: space(3.5),
    ...shadow.md,
  },

  row: { flexDirection: "row", alignItems: "center", gap: space(2.5) },
  rowBody: { flex: 1, minWidth: 0 },
  nameRow: { flexDirection: "row", alignItems: "center", gap: space(1.5) },
  name: { flexShrink: 1, fontFamily: family.bodySemi, fontSize: 15, color: colors.ink },
  meta: { fontFamily: family.body, fontSize: 12, color: colors.muted, marginTop: 2 },
  metaTiny: { fontFamily: family.body, fontSize: 11, color: colors.muted, marginTop: 1 },

  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: space(1.5), marginTop: space(3) },
  chipPale: {
    backgroundColor: colors.surface2,
    borderRadius: radius.pill,
    paddingHorizontal: space(2.5),
    paddingVertical: space(1),
  },
  chipRowTight: { marginTop: 0 },
  chipPaleText: { fontFamily: family.bodyMedium, fontSize: 11, color: colors.ink },
  chipTeal: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    backgroundColor: colors.tealSoft,
    borderRadius: radius.pill,
    paddingHorizontal: space(2),
    paddingVertical: space(0.75),
  },
  chipTealText: { fontFamily: family.bodySemi, fontSize: 10.5, color: colors.ink },

  cardFoot: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space(2),
    marginTop: space(3),
  },
  price: { fontFamily: family.bodyBold, fontSize: 15, color: colors.indigo },
  cardBtn: {
    backgroundColor: colors.indigo,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(1.75),
  },
  cardBtnText: { fontFamily: family.bodySemi, fontSize: 11.5, color: colors.white },

  headRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space(2) },
  cardTitle: { flexShrink: 1, fontFamily: family.bodySemi, fontSize: 13.5, color: colors.ink },
  amount: { fontFamily: family.display, fontSize: 24, color: colors.indigo, marginTop: space(2), letterSpacing: -0.4 },
  divider: { height: 1, backgroundColor: colors.line, marginVertical: space(2.5) },

  stepRow: { flexDirection: "row", alignItems: "center", gap: space(2), paddingVertical: space(0.75) },
  tickOn: { width: 18, height: 18, borderRadius: 9, backgroundColor: colors.teal, alignItems: "center", justifyContent: "center" },
  tickOff: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, borderColor: colors.line },
  stepLabel: { flexShrink: 1, fontFamily: family.bodyMedium, fontSize: 12.5, color: colors.ink },
  stepLabelPending: { fontFamily: family.body, color: colors.muted },

  starRow: { flexDirection: "row", alignItems: "center", gap: 1 },
  rating: { fontFamily: family.bodySemi, fontSize: 12.5, color: colors.ink, marginLeft: space(1.5) },
  quote: { fontFamily: family.body, fontSize: 12.5, color: colors.ink, lineHeight: 18, marginTop: space(2.5) },
  whoRow: { flexDirection: "row", alignItems: "center", gap: space(2), marginTop: space(2.5) },
  who: { fontFamily: family.bodySemi, fontSize: 12, color: colors.ink },
});
