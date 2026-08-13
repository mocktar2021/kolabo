import { useCallback, useEffect, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, mediaSrc, uploadMedia, type LocalImage, type MediaOut } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { pickImages } from "../../lib/imagePicker";
import { Banner, GhostButton, Hint, PrimaryButton, SectionTitle } from "../ui";
import { colors, family, font, radius, space } from "../../theme";

type PortfolioItem = { id: string; media_id: string; url: string };

/* One gallery trip may return several photos; the picker's cap and the slice
   inside pickImages both honour this. Ten is generous for a pilot portfolio
   and small enough that a full batch is still a bounded wait on 3G. */
const MAX_BATCH = 10;

/* The visual half of the storefront: work a creator wants seen. Upload and
   attach are two steps against two endpoints — POST /profiles/{id}/media for
   the bytes, then POST /profiles/{id}/portfolio with the media id — mirroring
   the web ProfileSetup flow, so a failed attach never strands a half-added
   card in the UI: the list is always reloaded from the server's answer.

   SELECTION IS A STAGE, NOT A SEND. Picking photos fills a pending strip
   where each one can still be removed; nothing uploads until the person says
   so. Uploads then run ONE AT A TIME, deliberately: the pilot's phones are on
   mobile data where parallel uploads starve each other, and a sequential loop
   gives an honest "3 / 8" counter and a precise failure story — everything
   before the failed photo is attached and stays attached, everything from it
   onwards is still pending and can be retried with one tap. */
export function PortfolioSection({ userId, token }: { userId: string; token: string | null }) {
  const { t } = useTranslation();
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [pending, setPending] = useState<LocalImage[]>([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await api<PortfolioItem[]>(`/profiles/${userId}/portfolio`, { token }));
    } catch {
      // A failed list read leaves the previous state; the add path reloads.
    }
  }, [userId, token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function choose() {
    const files = await pickImages(MAX_BATCH - pending.length);
    if (files.length === 0) return;
    setError(null);
    setPending((prev) => [...prev, ...files].slice(0, MAX_BATCH));
  }

  function unstage(index: number) {
    setPending((prev) => prev.filter((_, i) => i !== index));
  }

  async function uploadAll() {
    if (pending.length === 0) return;
    setBusy(true);
    setError(null);
    setProgress(0);
    const queue = [...pending];
    let sent = 0;
    try {
      for (const file of queue) {
        const media = await uploadMedia<MediaOut>(`/profiles/${userId}/media`, file, token);
        await api(`/profiles/${userId}/portfolio`, { method: "POST", token, body: { media_id: media.id } });
        sent += 1;
        setProgress(sent);
        // Drop each photo from the strip the moment it is safely attached,
        // so a mid-batch failure leaves exactly the unsent ones staged.
        setPending((prev) => prev.slice(1));
      }
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
      setProgress(0);
      await load();
    }
  }

  async function remove(itemId: string) {
    try {
      await api(`/profiles/${userId}/portfolio/${itemId}`, { method: "DELETE", token });
    } catch {
      // ignore; reload reflects true state
    }
    await load();
  }

  return (
    <View>
      <SectionTitle>{t("profile.portfolioTitle")}</SectionTitle>
      <Hint>{t("profile.portfolioHint")}</Hint>
      {error ? <Banner kind="error">{error}</Banner> : null}

      {items.length > 0 ? (
        <View style={styles.grid}>
          {items.map((item) => (
            <View key={item.id} style={styles.cell}>
              <Image source={{ uri: mediaSrc(item.url) }} style={styles.image} />
              <Text style={styles.remove} onPress={() => void remove(item.id)}>
                {t("profile.remove")}
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      {pending.length > 0 ? (
        <>
          <Text style={styles.pendingTitle}>
            {busy
              ? t("profile.portfolioUploading", { done: progress, total: progress + pending.length })
              : t("profile.portfolioPending", { n: pending.length })}
          </Text>
          <View style={styles.grid}>
            {pending.map((file, index) => (
              <View key={`${file.uri}-${index}`} style={styles.cell}>
                <Image source={{ uri: file.uri }} style={[styles.image, busy && index === 0 && styles.uploading]} />
                {!busy ? (
                  <Pressable onPress={() => unstage(index)} hitSlop={6}>
                    <Text style={styles.remove}>{t("profile.remove")}</Text>
                  </Pressable>
                ) : null}
              </View>
            ))}
          </View>
        </>
      ) : null}

      <View style={{ marginTop: space(2), gap: space(2) }}>
        {pending.length > 0 ? (
          <PrimaryButton
            title={
              busy
                ? t("profile.portfolioUploading", { done: progress, total: progress + pending.length })
                : t("profile.portfolioUpload", { n: pending.length })
            }
            onPress={() => void uploadAll()}
            loading={busy}
          />
        ) : null}
        <GhostButton
          title={t("profile.portfolioAdd")}
          onPress={() => void choose()}
          disabled={busy || pending.length >= MAX_BATCH}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap", gap: space(2), marginTop: space(2) },
  cell: { alignItems: "center" },
  image: {
    width: 96,
    height: 96,
    borderRadius: radius.sm,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.line,
  },
  uploading: { opacity: 0.5, borderColor: colors.indigo },
  pendingTitle: {
    fontSize: font.small,
    fontFamily: family.bodySemi,
    color: colors.ink,
    marginTop: space(3),
  },
  remove: { fontSize: font.tiny, color: colors.danger, fontFamily: family.bodySemi, marginTop: space(1) },
});
