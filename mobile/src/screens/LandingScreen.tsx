import { useCallback, useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useFocusEffect } from "@react-navigation/native";
import { useTranslation } from "react-i18next";
import { SlideArt } from "../components/landing";
import { LanguageSwitch } from "../components/LanguageSwitch";
import { Button } from "../components/ui";
import { markLandingSeen } from "../lib/onboarding";
import { colors, family, radius, space } from "../theme";
import type { AuthScreenProps } from "../navigation/types";
/* Side-effect import: every landing.* key below is registered on i18n at
   runtime by this module (the convention lib/paymentStrings.ts set). Without
   the import the screen renders the key names. */
import "../lib/landingStrings";

/* The pre-auth root: what a fresh install opens on, ahead of Login.

   THREE SLIDES, ONE STRUCTURE. A pale panel carrying a drawing of a real
   product surface, then the promise that surface makes, then the same two
   doors on every slide. The doors live OUTSIDE the pager on purpose: they are
   identical on all three slides, so paging them would animate a button out
   and an identical one in, and it would take the only two tap targets on the
   screen out from under the reader's thumb while a swipe was settling.

   THERE IS NO "CONTINUE WITH GOOGLE" BUTTON HERE, and the reason is no
   longer the one this note used to give. Google sign in exists now: the API
   answers POST /auth/google, core/config.py carries GOOGLE_CLIENT_IDS, and
   both clients ship a provider SDK. Every clause of the old note is false and
   it is replaced rather than deleted, because somebody will ask again.

   The button lives on Login and on Register instead, which is one tap from
   either door above. It is not on this screen for a reason that is about this
   screen: the register form collects a role and a country and sends them with
   the credential on the first call, and nothing on a carousel asks either
   question, so a button here would either sign people up as whatever the
   defaults happen to say or open the second step panel that LoginScreen
   already owns. Neither is worth putting on the slide whose whole job is to
   get somebody to one of the two doors underneath.

   THE LANGUAGE CONTROL IS HERE, on the other hand, and down with the doors
   rather than up on the art. See the note on it below. */

type Slide = {
  headA: string;
  headAccent: string;
  headB: string;
  body: string;
};

/* Keys, not template literals, so every string this screen can render is
   greppable from this file. */
const SLIDES: Slide[] = [
  {
    headA: "landing.s1HeadA",
    headAccent: "landing.s1HeadAccent",
    headB: "landing.s1HeadB",
    body: "landing.s1Body",
  },
  {
    headA: "landing.s2HeadA",
    headAccent: "landing.s2HeadAccent",
    headB: "landing.s2HeadB",
    body: "landing.s2Body",
  },
  {
    headA: "landing.s3HeadA",
    headAccent: "landing.s3HeadAccent",
    headB: "landing.s3HeadB",
    body: "landing.s3Body",
  },
];

/* Five seconds a slide, the same beat web/src/pages/Landing.tsx gives its
   workflow rotation. */
const AUTO_ADVANCE_MS = 5000;

/* Below this the handset is short enough that the headline, the body and two
   54 dp buttons stop fitting comfortably under the panel, so the type steps
   down a notch and the gaps tighten. Designed at 360 dp wide first; the
   longest French string here is the slide 2 body, which wraps to four lines
   at that width and still clears the buttons. */
const COMPACT_HEIGHT = 700;

export default function LandingScreen({ navigation }: AuthScreenProps<"Landing">) {
  const { t } = useTranslation();
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const listRef = useRef<FlatList<Slide>>(null);

  const [index, setIndex] = useState(0);
  /* Bumped by any deliberate touch — a drag starting, a drag ending, a dot
     tapped. It is a dependency of the auto-advance effect and of nothing
     else, so incrementing it tears down the pending timer and starts a fresh
     five seconds. That is the whole of "swiping resets the clock", and it is
     the difference between a carousel you can read and one that jumps out
     from under you two seconds after you took hold of it. */
  const [nudge, setNudge] = useState(0);
  /* False while the screen is off-screen (the reader is on Login, or on
     Register, with this one still mounted underneath). A pager that keeps
     counting in the background wakes up on a slide nobody chose. */
  const [focused, setFocused] = useState(true);
  const [reduceMotion, setReduceMotion] = useState(false);

  const compact = height < COMPACT_HEIGHT;
  /* Roughly the top 45% the design asks for, floored so the card never
     crops on a short handset and capped so it does not swallow a tall one. */
  const panelHeight = Math.round(Math.min(Math.max(height * 0.42, 250), 360));

  /* Reduce motion is read once and then watched: it can be switched on from
     the system settings while the app is open, and a reader who has just
     turned it on should not have to relaunch to be left alone. */
  useEffect(() => {
    let active = true;
    void AccessibilityInfo.isReduceMotionEnabled().then((on) => {
      if (active) setReduceMotion(on);
    });
    const sub = AccessibilityInfo.addEventListener("reduceMotionChanged", (on) => {
      setReduceMotion(on);
    });
    return () => {
      active = false;
      sub.remove();
    };
  }, []);

  useFocusEffect(
    useCallback(() => {
      setFocused(true);
      return () => setFocused(false);
    }, [])
  );

  /* The one place the pager is moved from code. It animates unless reduce
     motion is on, in which case even a tapped dot lands instantly: the
     setting is about movement the reader did not ask for on screen, and a
     300 ms slide is exactly that even when a tap started it. */
  const goTo = useCallback(
    (i: number) => {
      setIndex(i);
      listRef.current?.scrollToOffset({ offset: i * width, animated: !reduceMotion });
    },
    [width, reduceMotion]
  );

  /* THE AUTO-ADVANCE. A timeout rather than an interval, restarted from
     scratch whenever the slide changes or the reader touches the pager, which
     is what makes "reset the clock" fall out of the dependency list instead
     of needing to be arranged.

     Two ways it does not run at all:
     - reduce motion: no timer is ever created, so the carousel is purely
       manual. Same guard, same reason, as the web landing's rotation.
     - unfocused: the effect tears down when the screen loses focus and
       rebuilds when it comes back, so the five seconds start again from the
       slide the reader left on rather than from wherever a background timer
       had got to. */
  useEffect(() => {
    if (reduceMotion || !focused) return;
    const id = setTimeout(() => goTo((index + 1) % SLIDES.length), AUTO_ADVANCE_MS);
    return () => clearTimeout(id);
  }, [index, nudge, focused, reduceMotion, goTo]);

  /* Keep the pager on the slide it was on if the viewport width changes. */
  useEffect(() => {
    listRef.current?.scrollToOffset({ offset: index * width, animated: false });
    // Deliberately only on width: goTo already scrolls when the index moves.
  }, [width]); // eslint-disable-line react-hooks/exhaustive-deps

  const touched = useCallback(() => setNudge((n) => n + 1), []);

  const onMomentumEnd = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      const raw = Math.round(e.nativeEvent.contentOffset.x / width);
      const next = Math.max(0, Math.min(SLIDES.length - 1, raw));
      setIndex(next);
      setNudge((n) => n + 1);
    },
    [width]
  );

  /* Both doors mark the intro as seen: the flag means "has been through it
     and chosen", so a returning signed-out user lands straight on Login. */
  const openRegister = useCallback(() => {
    void markLandingSeen();
    navigation.navigate("Register");
  }, [navigation]);

  const openLogin = useCallback(() => {
    void markLandingSeen();
    navigation.navigate("Login");
  }, [navigation]);

  const renderItem = useCallback(
    ({ item, index: i }: { item: Slide; index: number }) => {
      const headline = `${t(item.headA)}${t(item.headAccent)}${t(item.headB)}`;
      return (
        <View style={{ width }}>
          <SlideArt index={i} height={panelHeight + insets.top} topInset={insets.top} />
          <View style={[styles.copy, compact && styles.copyCompact]}>
            <View style={styles.dots}>
              {SLIDES.map((_, d) => (
                <Pressable
                  key={d}
                  onPress={() => {
                    setNudge((n) => n + 1);
                    goTo(d);
                  }}
                  hitSlop={10}
                  accessibilityRole="button"
                  accessibilityLabel={t("landing.a11yGoToSlide", { n: d + 1 })}
                  style={[styles.dot, d === index && styles.dotActive]}
                />
              ))}
            </View>
            <Text
              style={[styles.headline, compact && styles.headlineCompact]}
              accessibilityLabel={`${t("landing.a11ySlide", { n: i + 1, total: SLIDES.length })}. ${headline}`}
            >
              {t(item.headA)}
              <Text style={styles.accent}>{t(item.headAccent)}</Text>
              {t(item.headB)}
            </Text>
            <Text style={[styles.body, compact && styles.bodyCompact]}>{t(item.body)}</Text>
          </View>
        </View>
      );
    },
    [t, width, panelHeight, insets.top, compact, index, goTo]
  );

  return (
    <View style={styles.root}>
      <FlatList
        ref={listRef}
        data={SLIDES}
        renderItem={renderItem}
        keyExtractor={(_, i) => String(i)}
        /* The active dot is the only thing in a slide that depends on state
           outside it, and FlatList memoises its cells — without this the dots
           freeze on slide 1. */
        extraData={index}
        horizontal
        pagingEnabled
        bounces={false}
        showsHorizontalScrollIndicator={false}
        onScrollBeginDrag={touched}
        onScrollEndDrag={touched}
        onMomentumScrollEnd={onMomentumEnd}
        getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
        initialNumToRender={SLIDES.length}
        windowSize={SLIDES.length}
        style={styles.pager}
      />
      <View style={[styles.cta, compact && styles.ctaCompact, { paddingBottom: insets.bottom + space(4) }]}>
        <Button title={t("landing.ctaRegister")} onPress={openRegister} variant="primary" size="lg" />
        {/* The house Button has no pale-lavender variant and this is the only
            screen that wants one, so it is stated here — on the same metrics
            as Button size="lg" above, so the pair reads as one control. */}
        <Pressable
          onPress={openLogin}
          accessibilityRole="button"
          style={({ pressed }) => [styles.soft, pressed && styles.softPressed]}
        >
          <Text style={styles.softText}>{t("landing.ctaLogin")}</Text>
        </Pressable>
        {/* THE ONE CONTROL ON THIS SCREEN THAT IS NOT A DOOR, and the reason
            it is down here rather than up in a corner: the panel above draws
            under insets.top by design, so anything floating over it would sit
            on the art and fight it, and the art is the slide. Here it rides
            outside the pager with the two buttons, where a thumb already is,
            at the exact moment somebody is deciding whether this app is for
            them. A visitor whose phone is set to neither of our languages
            lands in French (src/i18n.ts), and until now the first way out of
            that was the account screen, which is behind registering. */}
        <View style={styles.lang}>
          <LanguageSwitch />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.white },
  pager: { flex: 1 },

  copy: { paddingHorizontal: space(6), paddingTop: space(5) },
  copyCompact: { paddingTop: space(4) },

  dots: { flexDirection: "row", alignItems: "center", gap: space(1.5), marginBottom: space(4) },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.line },
  dotActive: { width: 20, backgroundColor: colors.indigo },

  headline: {
    fontFamily: family.display,
    fontSize: 26,
    lineHeight: 33,
    letterSpacing: -0.5,
    color: colors.ink,
  },
  headlineCompact: { fontSize: 23, lineHeight: 29 },
  /* Teal on white at this weight and size clears the 3:1 large-text floor;
     it would not at body size, which is why only the headline uses it. */
  accent: { color: colors.teal600 },
  body: {
    fontFamily: family.body,
    fontSize: 15,
    lineHeight: 22,
    color: colors.muted,
    marginTop: space(2.5),
  },
  bodyCompact: { fontSize: 14, lineHeight: 20, marginTop: space(2) },

  cta: { paddingHorizontal: space(6), paddingTop: space(3), gap: space(2.5) },
  /* Centred under the two doors. The pill sets alignSelf: "flex-start" on
     itself so it never stretches, which is what makes centring it a matter of
     this one line. */
  lang: { alignItems: "center" },
  ctaCompact: { paddingTop: space(2), gap: space(2) },
  soft: {
    backgroundColor: colors.surface2,
    borderRadius: radius.sm,
    paddingVertical: space(3.5),
    paddingHorizontal: space(5),
    minHeight: 54,
    alignItems: "center",
    justifyContent: "center",
  },
  softPressed: { backgroundColor: colors.line },
  softText: { fontFamily: family.bodySemi, fontSize: 16, color: colors.indigo },
});
