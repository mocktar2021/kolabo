import type { ReactNode } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, font, radius, space } from "../theme";

/* A screen shell: safe area, keyboard avoidance, and a scroll view so a form
   stays reachable above the keyboard on a small phone. */
export function Screen({ children }: { children: ReactNode }) {
  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
        >
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
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

export function Hint({ children }: { children: ReactNode }) {
  return <Text style={styles.hint}>{children}</Text>;
}

export function Field({
  label,
  hint,
  ...rest
}: { label: string; hint?: string } & TextInputProps) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={styles.input}
        placeholderTextColor={colors.muted}
        {...rest}
      />
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

export function PrimaryButton({
  title,
  onPress,
  disabled,
  loading,
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
}) {
  const off = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      style={({ pressed }) => [
        styles.btn,
        styles.btnPrimary,
        off && styles.btnDisabled,
        pressed && !off && styles.btnPressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={colors.white} />
      ) : (
        <Text style={styles.btnPrimaryText}>{title}</Text>
      )}
    </Pressable>
  );
}

export function GhostButton({
  title,
  onPress,
  disabled,
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.btn,
        styles.btnGhost,
        disabled && styles.btnDisabled,
        pressed && !disabled && { backgroundColor: colors.surface },
      ]}
    >
      <Text style={styles.btnGhostText}>{title}</Text>
    </Pressable>
  );
}

export function Banner({
  kind,
  children,
}: {
  kind: "error" | "info" | "success";
  children: ReactNode;
}) {
  const tone =
    kind === "error"
      ? { bg: "#fdecec", fg: colors.danger }
      : kind === "success"
        ? { bg: "#e7f6f0", fg: colors.success }
        : { bg: colors.surface2, fg: colors.ink };
  return (
    <View style={[styles.banner, { backgroundColor: tone.bg }]}>
      <Text style={[styles.bannerText, { color: tone.fg }]}>{children}</Text>
    </View>
  );
}

/* A single-select row of pill options — used for the role and country pickers.
   React Native has no native <select>; a wrapped chip row is the mobile-native
   equivalent and keeps taps large. */
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

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.surface },
  flex: { flex: 1 },
  scroll: { padding: space(5), paddingBottom: space(10), justifyContent: "center", flexGrow: 1 },
  card: {
    backgroundColor: colors.white,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: space(5),
  },
  title: { fontSize: font.h1, fontWeight: "700", color: colors.ink, marginBottom: space(1) },
  subtitle: { fontSize: font.body, color: colors.muted, marginBottom: space(4) },
  label: { fontSize: font.small, fontWeight: "600", color: colors.ink, marginBottom: space(1.5) },
  hint: { fontSize: font.tiny, color: colors.muted, marginTop: space(1.5) },
  field: { marginBottom: space(4) },
  input: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(3),
    fontSize: font.body,
    color: colors.ink,
    backgroundColor: colors.white,
  },
  btn: {
    borderRadius: radius.sm,
    paddingVertical: space(3.5),
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  btnPrimary: { backgroundColor: colors.teal },
  btnPressed: { backgroundColor: colors.teal600 },
  btnPrimaryText: { color: colors.white, fontSize: font.body, fontWeight: "700" },
  btnGhost: { backgroundColor: "transparent", borderWidth: 1, borderColor: colors.line },
  btnGhostText: { color: colors.ink, fontSize: font.body, fontWeight: "600" },
  btnDisabled: { opacity: 0.5 },
  banner: { borderRadius: radius.sm, padding: space(3), marginBottom: space(4) },
  bannerText: { fontSize: font.small },
  choiceWrap: { flexDirection: "row", flexWrap: "wrap", gap: space(2) },
  choice: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(2.5),
    minWidth: 92,
  },
  choiceSelected: { borderColor: colors.teal, backgroundColor: colors.tealSoft },
  choiceLabel: { fontSize: font.small, fontWeight: "600", color: colors.ink },
  choiceLabelSelected: { color: colors.teal600 },
  choiceDesc: { fontSize: font.tiny, color: colors.muted, marginTop: 2, maxWidth: 220 },
});
