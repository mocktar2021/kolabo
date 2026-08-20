import { useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { mediaSrc, uploadMedia, type MediaOut } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { pickImage } from "../../lib/imagePicker";
import { GhostButton, Hint } from "../ui";
import { colors, family, font, radius, space } from "../../theme";

/* Mirrors MAX_EVIDENCE_IMAGES in backend/app/modules/payments/disputes.py, so
   the cap is met as a disabled button rather than as a 400 after the upload.
   Only the DEFAULT: a caller with a different ceiling passes its own, which
   the deliverables panel does (MAX_ATTACHMENTS is a different constant in a
   different module and only happens to be the same number today). */
const MAX_EVIDENCE = 10;

/* Images attached to something the other party has to look at. Mirror of the
   web EvidencePicker: they upload immediately via the shared profile-media
   endpoint (attachments are stored media like any other), and the PARENT owns
   the resulting id list — this control reports ids up and renders thumbnails,
   so the form submits {media_ids} it has already verified are uploaded. One
   image per pick: the native multi-select is uneven across launchers, and the
   button stays available until the cap, so a second photo is a second tap.

   NOT DISPUTE-ONLY ANY MORE, and only the LABEL was. The deliverables panel
   attaches proof of published work through this same uploader — "Screenshots"
   is the wrong word for a creator handing in the photos they were hired to
   shoot — so the label became a prop rather than this becoming a second
   uploader. Everything worth having exactly once stays here: the upload path,
   the cap, and the ownership guarantee. Uploading through the caller's OWN
   /profiles/{userId}/media is what makes the server's ownership check
   (deliverables.service._checked_media, disputes' twin of it) pass by
   construction.

   THE FAILURE IS THE SERVER'S SENTENCE, NOT OURS. This used to answer every
   failure with one invented line, "The image could not be uploaded", which
   hides the two refusals a phone actually hits: a file over the 10 MB ceiling
   (413 profile_file_too_large, which carries the ceiling as a number so the
   sentence can quote it) and a format the API does not take (400
   profile_image_type_unsupported). Both are already written out in both
   languages in lib/errorMessages.ts, and both tell the person what to do
   next; errorText also names a dead radio rather than blaming the image. */
export function EvidencePicker({ userId, token, value, onChange, label, max = MAX_EVIDENCE }: {
  userId: string;
  token: string | null;
  value: MediaOut[];
  onChange: (next: MediaOut[]) => void;
  /* Overrides the field label for callers that are not a dispute. Optional, so
     every existing dispute caller keeps its copy unchanged. */
  label?: string;
  /* The caller's own ceiling, when its endpoint enforces a different one. */
  max?: number;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function add() {
    if (value.length >= max) return;
    const file = await pickImage();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const media = await uploadMedia<MediaOut>(`/profiles/${userId}/media`, file, token);
      onChange([...value, media]);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ marginBottom: space(3) }}>
      <Text style={styles.label}>{label ?? t("dispute.evidence")}</Text>
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
      {value.length >= max ? (
        <Hint>{t("dispute.evidenceMax", { n: max })}</Hint>
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
  label: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) },
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
  remove: { fontSize: font.tiny, color: colors.danger, fontFamily: family.bodySemi, marginTop: 3 },
});
