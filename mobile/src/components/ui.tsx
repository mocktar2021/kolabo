import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Animated,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, family, font, radius, shadow, space } from "../theme";

/* The shared primitives, restyled to match web/src/styles/theme.css so the
   two clients read as one product: indigo primary buttons (.btn-primary),
   teal as secondary emphasis (.btn-teal), Poppins display type on headings,
   Inter body type, shadowed cards, and the same alert palette.

   The export surface is kept compatible with every existing screen —
   PrimaryButton/GhostButton remain — so restyling here restyles the whole
   app without editing a screen. New in this pass: Button (the variant engine
   both wrap), Spinner, Skeleton, and a Screen that can own the loading and
   pull-to-refresh states, so screens stop hand-rolling `loading ? null`. */

/* A screen shell: safe area, keyboard avoidance, and a scroll view so a form
   stays reachable above the keyboard on a small phone.

   `loading` renders a centred spinner INSTEAD of children — the fix for the
   blank-while-loading screens. `onRefresh` mounts the native pull-to-refresh
   control; the spinner it shows is brand indigo. */
export function Screen({
  children,
  loading = false,
  refreshing = false,
  onRefresh,
}: {
  children: ReactNode;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {loading ? (
          <Spinner />
        ) : (
          <ScrollView
            contentContainerStyle={styles.scroll}
            keyboardShouldPersistTaps="handled"
            refreshControl={
              onRefresh ? (
                <RefreshControl
                  refreshing={refreshing}
                  onRefresh={onRefresh}
                  colors={[colors.indigo]}
                  tintColor={colors.indigo}
                />
              ) : undefined
            }
          >
            {children}
          </ScrollView>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

/* Centred brand spinner — what a screen shows while its first load is in
   flight. Web shows a "Loading…" line; a native spinner is the same promise
   in the platform's own language. */
export function Spinner() {
  return (
    <View style={styles.spinnerWrap}>
      <ActivityIndicator color={colors.indigo} size="large" />
    </View>
  );
}

/* A pulsing placeholder block for list skeletons. Opacity animation rather
   than a shimmer: no extra dependency, and the pulse reads clearly as
   "content coming" at every speed. */
export function Skeleton({
  height = 16,
  width,
  round = false,
}: {
  height?: number;
  width?: number | `${number}%`;
  round?: boolean;
}) {
  const opacity = useRef(new Animated.Value(0.5)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 600, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.5, duration: 600, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);
  return (
    <Animated.View
      style={{
        opacity,
        height,
        width: width ?? "100%",
        borderRadius: round ? height / 2 : radius.sm,
        backgroundColor: colors.surface2,
      }}
    />
  );
}

export function Card({ children }: { children: ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}

export function Title({ children }: { children: ReactNode }) {
  return <Text style={styles.title}>{children}</Text>;
}

export function Subtitle({ children }: { children: ReactNode }) {
  return <Text style={styles.subtitle}>{children}</Text>;
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <Text style={styles.sectionTitle}>{children}</Text>;
}

export function Hint({ children }: { children: ReactNode }) {
  return <Text style={styles.hint}>{children}</Text>;
}

export function Field({
  label,
  hint,
  secureTextEntry,
  ...rest
}: { label: string; hint?: string } & TextInputProps) {
  /* Web inputs get a focus ring (border + soft glow); RN has no box-shadow,
     so the border carries the state alone. */
  const [focused, setFocused] = useState(false);
  /* Every secure field gets an eye toggle for free: on a phone keyboard,
     typing a password blind is how typos become lockouts. `hidden` is this
     field's own state, so revealing one password never reveals another. */
  const [hidden, setHidden] = useState(true);
  const secure = !!secureTextEntry;
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <View>
        <TextInput
          style={[styles.input, secure && styles.inputSecure, focused && styles.inputFocused]}
          placeholderTextColor={colors.muted}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          secureTextEntry={secure && hidden}
          {...rest}
        />
        {secure ? (
          <Pressable
            onPress={() => setHidden((v) => !v)}
            hitSlop={8}
            style={styles.eye}
            accessibilityRole="button"
            accessibilityLabel={hidden ? "Show password" : "Hide password"}
          >
            <Ionicons name={hidden ? "eye-outline" : "eye-off-outline"} size={20} color={colors.muted} />
          </Pressable>
        ) : null}
      </View>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

/* One button, three faces — the web's .btn-primary (indigo), .btn-teal and
   .btn-ghost, with the same pressed darkening and disabled dimming. size
   "lg" mirrors .btn-lg for hero CTAs. */
export type ButtonVariant = "primary" | "teal" | "ghost";

export function Button({
  title,
  onPress,
  variant = "primary",
  size,
  disabled,
  loading,
}: {
  title: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: "lg";
  disabled?: boolean;
  loading?: boolean;
}) {
  const off = disabled || loading;
  const base =
    variant === "primary"
      ? styles.btnPrimary
      : variant === "teal"
        ? styles.btnTeal
        : styles.btnGhost;
  const pressed =
    variant === "primary"
      ? styles.btnPrimaryPressed
      : variant === "teal"
        ? styles.btnTealPressed
        : styles.btnGhostPressed;
  const textStyle = variant === "ghost" ? styles.btnGhostText : styles.btnSolidText;
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      style={({ pressed: isPressed }) => [
        styles.btn,
        base,
        size === "lg" && styles.btnLg,
        off && styles.btnDisabled,
        isPressed && !off && pressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={variant === "ghost" ? colors.ink : colors.white} />
      ) : (
        <Text style={[textStyle, size === "lg" && styles.btnLgText]}>{title}</Text>
      )}
    </Pressable>
  );
}

/* The two names every existing screen already imports. Primary is now
   indigo, as it is on web — teal was standing in for it before. */
export function PrimaryButton(props: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
}) {
  return <Button {...props} variant="primary" />;
}

export function GhostButton(props: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return <Button {...props} variant="ghost" />;
}

export function Banner({
  kind,
  children,
}: {
  kind: "error" | "info" | "success";
  children: ReactNode;
}) {
  /* Web's .alert palette, verbatim: soft field, readable dark text, hairline
     border in the same hue. */
  const tone =
    kind === "error"
      ? { bg: "#fdecec", fg: "#9b2c2c", border: "#f5c6c6" }
      : kind === "success"
        ? { bg: "#e7f6f0", fg: "#12694f", border: "#b8e4d3" }
        : { bg: "#eef1f8", fg: "#2f3a63", border: "#d5dcf0" };
  return (
    <View style={[styles.banner, { backgroundColor: tone.bg, borderColor: tone.border }]}>
      <Text style={[styles.bannerText, { color: tone.fg }]}>{children}</Text>
    </View>
  );
}

/* A single-select row of pill options — used for the role and country pickers.
   React Native has no native <select>; a wrapped chip row is the mobile-native
   equivalent and keeps taps large. Selected state mirrors the web .segment:
   indigo border, surface-2 field. */
export type Choice = { value: string; label: string; description?: string };

export function ChoiceGroup({
  options,
  value,
  onChange,
}: {
  options: Choice[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <View style={styles.choiceWrap}>
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <Pressable
            key={o.value}
            onPress={() => onChange(o.value)}
            style={[styles.choice, selected && styles.choiceSelected]}
          >
            <Text style={[styles.choiceLabel, selected && styles.choiceLabelSelected]}>
              {o.label}
            </Text>
            {o.description ? (
              <Text style={styles.choiceDesc}>{o.description}</Text>
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}

/* The mobile <select>: a field-shaped trigger that opens a modal option
   sheet. This is what long single-choice lists (countries, cities) use —
   a seven-country chip grid was eating half the register screen; a dropdown
   is one row, exactly as the web renders its <select>. ChoiceGroup remains
   the right shape for short lists (roles, genders) where seeing every option
   at once helps. */
export function Select({
  label,
  value,
  options,
  onChange,
  placeholder,
  hint,
}: {
  label?: string;
  value: string;
  options: Choice[];
  onChange: (v: string) => void;
  placeholder?: string;
  hint?: string;
}) {
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value);
  return (
    <View style={styles.field}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <Pressable
        accessibilityRole="button"
        onPress={() => setOpen(true)}
        style={({ pressed }) => [styles.selectBox, pressed && { backgroundColor: colors.surface }]}
      >
        <Text style={[styles.selectValue, !current && { color: colors.muted }]} numberOfLines={1}>
          {current ? current.label : (placeholder ?? "")}
        </Text>
        <Ionicons name="chevron-down" size={18} color={colors.muted} />
      </Pressable>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.selectBackdrop} onPress={() => setOpen(false)}>
          {/* The sheet itself swallows taps so choosing doesn't also dismiss-through. */}
          <Pressable style={styles.selectSheet} onPress={() => undefined}>
            {label ? <Text style={styles.selectSheetTitle}>{label}</Text> : null}
            <ScrollView style={{ flexGrow: 0 }}>
              {options.map((o) => {
                const selected = o.value === value;
                return (
                  <Pressable
                    key={o.value}
                    onPress={() => {
                      onChange(o.value);
                      setOpen(false);
                    }}
                    style={({ pressed }) => [
                      styles.selectRow,
                      pressed && { backgroundColor: colors.surface },
                    ]}
                  >
                    <Text style={[styles.selectRowLabel, selected && styles.selectRowSelected]}>
                      {o.label}
                    </Text>
                    {selected ? <Ionicons name="checkmark" size={18} color={colors.indigo} /> : null}
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

/* The multi-select sibling of ChoiceGroup — categories, languages: tap to add
   or remove, no single-selection constraint. */
export function MultiChoiceGroup({
  options,
  values,
  onToggle,
}: {
  options: Choice[];
  values: string[];
  onToggle: (v: string) => void;
}) {
  return (
    <View style={styles.choiceWrap}>
      {options.map((o) => {
        const selected = values.includes(o.value);
        return (
          <Pressable
            key={o.value}
            onPress={() => onToggle(o.value)}
            style={[styles.choice, selected && styles.choiceSelected]}
          >
            <Text style={[styles.choiceLabel, selected && styles.choiceLabelSelected]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  scroll: { padding: space(5), paddingBottom: space(10), justifyContent: "center", flexGrow: 1 },
  spinnerWrap: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: {
    backgroundColor: colors.white,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: space(7),
    ...shadow.sm,
  },
  title: {
    fontSize: font.h1,
    fontFamily: family.display,
    color: colors.ink,
    letterSpacing: -0.3,
    marginBottom: space(1),
  },
  subtitle: {
    fontSize: font.body,
    fontFamily: family.body,
    color: colors.muted,
    marginBottom: space(4),
    lineHeight: 22,
  },
  sectionTitle: {
    fontSize: font.h2,
    fontFamily: family.displaySemi,
    color: colors.ink,
    letterSpacing: -0.2,
    marginTop: space(3),
    marginBottom: space(2),
  },
  label: {
    fontSize: font.small,
    fontFamily: family.bodySemi,
    color: colors.ink,
    marginBottom: space(1.5),
  },
  hint: { fontSize: font.tiny, fontFamily: family.body, color: colors.muted, marginTop: space(1.5), lineHeight: 17 },
  field: { marginBottom: space(4) },
  input: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(3),
    fontSize: font.body,
    fontFamily: family.body,
    color: colors.ink,
    backgroundColor: colors.white,
  },
  inputFocused: { borderColor: colors.indigo600 },
  inputSecure: { paddingRight: space(9) },
  eye: {
    position: "absolute",
    right: space(3),
    top: 0,
    bottom: 0,
    justifyContent: "center",
  },
  btn: {
    borderRadius: radius.sm,
    paddingVertical: space(3),
    paddingHorizontal: space(5),
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  btnLg: { paddingVertical: space(3.5), minHeight: 54 },
  btnPrimary: { backgroundColor: colors.indigo },
  btnPrimaryPressed: { backgroundColor: colors.indigo700 },
  btnTeal: { backgroundColor: colors.teal },
  btnTealPressed: { backgroundColor: colors.teal600 },
  btnGhost: { backgroundColor: "transparent", borderWidth: 1, borderColor: colors.line },
  btnGhostPressed: { backgroundColor: colors.surface },
  btnSolidText: { color: colors.white, fontSize: font.body, fontFamily: family.bodySemi },
  btnGhostText: { color: colors.ink, fontSize: font.body, fontFamily: family.bodySemi },
  btnLgText: { fontSize: 16 },
  btnDisabled: { opacity: 0.6 },
  banner: { borderRadius: radius.sm, borderWidth: 1, padding: space(3), marginBottom: space(4) },
  bannerText: { fontSize: font.small, fontFamily: family.body, lineHeight: 19 },
  selectBox: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space(2),
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(3),
    minHeight: 48,
    backgroundColor: colors.white,
  },
  selectValue: { flex: 1, fontSize: font.body, fontFamily: family.body, color: colors.ink },
  selectBackdrop: {
    flex: 1,
    backgroundColor: "rgba(21, 24, 36, 0.45)",
    justifyContent: "center",
    padding: space(5),
  },
  selectSheet: {
    backgroundColor: colors.white,
    borderRadius: radius.md,
    paddingVertical: space(2),
    maxHeight: "70%",
    ...shadow.md,
  },
  selectSheetTitle: {
    fontSize: font.small,
    fontFamily: family.bodySemi,
    color: colors.muted,
    paddingHorizontal: space(4),
    paddingVertical: space(2),
  },
  selectRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space(2),
    paddingHorizontal: space(4),
    paddingVertical: space(3.5),
  },
  selectRowLabel: { fontSize: font.body, fontFamily: family.body, color: colors.ink, flexShrink: 1 },
  selectRowSelected: { fontFamily: family.bodySemi, color: colors.indigo },
  choiceWrap: { flexDirection: "row", flexWrap: "wrap", gap: space(2) },
  choice: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(2.5),
    minWidth: 92,
    backgroundColor: colors.white,
  },
  choiceSelected: { borderColor: colors.indigo, backgroundColor: colors.surface2 },
  choiceLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink },
  choiceLabelSelected: { color: colors.indigo },
  choiceDesc: { fontSize: font.tiny, fontFamily: family.body, color: colors.muted, marginTop: 2, maxWidth: 220 },
});
