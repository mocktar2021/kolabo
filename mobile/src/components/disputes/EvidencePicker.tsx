import { useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { mediaSrc, uploadMedia, type MediaOut } from "../../lib/api";
import { pickImage } from "../../lib/imagePicker";
import { GhostButton, Hint } from "../ui";
import { colors, font, radius, space } from "../../theme";

/* Mirrors MAX_EVIDENCE_IMAGES in backend/app/modules/payments/disputes.py, so
   the cap is met as a disabled button rather than as a 400 after the upload. */
const MAX_EVIDENCE = 10;

/* Screenshots attached to a dispute claim or reply. Mirror of the web
   EvidencePicker: images upload immediately via the shared profile-media
   endpoint (evidence is stored media like any other), and the PARENT owns the
   resulting id list — this control reports ids up and renders thumbnails, so
   the form submits {media_ids} it has already verified are uploaded. One
   image per pick: the native multi-select is uneven across launchers, and a
   dispute rarely needs more than a handful. */
export function EvidencePicker({ userId, token, value, onChange }: {
  userId: string;
  token: string | null;
  value: MediaOut[];
  onChange: (next: MediaOut[]) => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function add() {
    if (value.length >= MAX_EVIDENCE) return;
    const file = await pickImage();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const media = await uploadMedia<MediaOut>(`/profiles/${userId}/media`, file, token);
      onChange([...value, media]);
    } catch {
      setError(t("dispute.evidenceFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ marginBottom: space(3) }}>
      <Text style={styles.label}>{t("dispute.evidence")}</Text>
      {value.length > 0 ? (
        <View style={styles.grid}>
          {value.map((m) => (
            <View key={m.id} style={styles.cell}>
              <Image source={{ uri: mediaSrc(m.url) }} style={styles.image} />
              <Text
                style={styles.remove}
                onPress={() => onChange(value.filter((x) => x.id !== m.id))}
              >
                {t("dispute.evidenceRemove")}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
      {error ? <Hint>{error}</Hint> : null}
      {value.length >= MAX_EVIDENCE ? (
        <Hint>{t("dispute.evidenceMax", { n: MAX_EVIDENCE })}</Hint>
      ) : (
        <View style={{ marginTop: space(1) }}>
          <GhostButton
            title={busy ? t("common.working") : t("dispute.evidenceAdd")}
            onPress={() => void add()}
            disabled={busy}
          />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  label: { fontSize: font.small, fontWeight: "600", color: colors.ink, marginBottom: space(1.5) },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: space(2), marginBottom: space(1) },
  cell: { alignItems: "center" },
  image: {
    width: 72,
    height: 72,
    borderRadius: radius.sm,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.line,
  },
  remove: { fontSize: font.tiny, color: colors.danger, fontWeight: "600", marginTop: 3 },
});
