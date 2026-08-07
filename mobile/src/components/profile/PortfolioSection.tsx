import { useCallback, useEffect, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api, mediaSrc, uploadMedia, type MediaOut } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { pickImage } from "../../lib/imagePicker";
import { Banner, GhostButton, Hint, SectionTitle } from "../ui";
import { colors, font, radius, space } from "../../theme";

type PortfolioItem = { id: string; media_id: string; url: string };

/* The visual half of the storefront: work a creator wants seen. Upload and
   attach are two steps against two endpoints — POST /profiles/{id}/media for
   the bytes, then POST /profiles/{id}/portfolio with the media id — mirroring
   the web ProfileSetup flow, so a failed attach never strands a half-added
   card in the UI: the list is always reloaded from the server's answer. */
export function PortfolioSection({ userId, token }: { userId: string; token: string | null }) {
  const { t } = useTranslation();
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [busy, setBusy] = useState(false);
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

  async function add() {
    const file = await pickImage();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const media = await uploadMedia<MediaOut>(`/profiles/${userId}/media`, file, token);
      await api(`/profiles/${userId}/portfolio`, { method: "POST", token, body: { media_id: media.id } });
      await load();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
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

      <View style={{ marginTop: space(2) }}>
        <GhostButton
          title={busy ? t("common.working") : t("profile.portfolioAdd")}
          onPress={() => void add()}
          disabled={busy}
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
  remove: { fontSize: font.tiny, color: colors.danger, fontWeight: "600", marginTop: space(1) },
});
