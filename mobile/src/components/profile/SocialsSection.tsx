import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import * as WebBrowser from "expo-web-browser";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { SOCIAL_PLATFORMS, platformHasAudience, type SocialPlatform } from "../../lib/socialPlatforms";
import { oauthReturnUrl, readCallbackParams } from "../../lib/socialConnect";
import { PLATFORM_LABELS } from "../../lib/platforms";
import type { SocialAccount } from "../../lib/profileTypes";
import { Banner, Button, Field, GhostButton, Hint, PrimaryButton, SectionTitle } from "../ui";
import { colors, family, font, radius, space } from "../../theme";
/* Imported for its side effect, the way PackagesSection imports
   packageStrings: the module registers the three profile.socialConnect* keys
   on i18n, and without this line every one of them renders as its own key. */
import "../../lib/socialConnectStrings";

/* Connected accounts, and the two ways a creator can add one.

   CONNECT is an OAuth handshake. POST /profiles/oauth/{platform}/start hands
   back an authorize_url, the system browser runs the platform's own consent
   screen, and the backend redirects into the app with the answer. Offered
   only where canConnect is true in lib/socialPlatforms, which today is
   Facebook and nothing else, because oauth.build_default_providers registers
   exactly one provider.

   TYPE A HANDLE is the path that was here first, and it stays. It goes in as
   a manual proof (status "pending"). A creator who will not hand us a token,
   or whose platform has no provider behind it, still gets to claim their
   name. Removing it would make seven of these eight tiles unclaimable.

   NEITHER PATH BADGES ANYTHING. Both land on status "pending", because
   oauth_service._account_for says so: a reviewed provider is a far better
   argument for a badge than a typed string was, and switching one on stays a
   decision somebody makes rather than one a plumbing change makes for them.
   What the handshake DOES earn is the follower number, read from the
   platform's own API against the creator's own token, which is why a
   successful connect reloads the list rather than patching a row.

   If the manual connect response says it enriched, the parent reloads so the
   auto-filled profile fields show at once. */
export function SocialsSection({
  userId,
  token,
  onChanged,
}: {
  userId: string;
  token: string | null;
  onChanged: () => void | Promise<void>;
}) {
  const { t } = useTranslation();
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [adding, setAdding] = useState<SocialPlatform | null>(null);
  const [handle, setHandle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enrichedNote, setEnrichedNote] = useState(false);
  /* The platform whose consent screen is open, or null. A platform id rather
     than a boolean so the spinner sits on the button that was actually
     tapped, which matters the day a second provider is registered. */
  const [connecting, setConnecting] = useState<string | null>(null);
  const [connectedNote, setConnectedNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setAccounts(await api<SocialAccount[]>(`/profiles/${userId}/social-accounts`, { token }));
    } catch {
      // A failed list is not worth an error state on this section.
    }
  }, [userId, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const connected = new Set(accounts.map((a) => a.platform));

  async function add() {
    if (!adding || !handle.trim()) return;
    setBusy(true);
    setError(null);
    const clean = handle.trim().replace(/^@/, "");
    try {
      const res = await api<SocialAccount>(`/profiles/${userId}/social-accounts`, {
        method: "POST",
        token,
        body: {
          platform: adding.id,
          handle: clean,
          method: "manual",
          proof_url: `https://${adding.prefix}${clean}`,
        },
      });
      setAdding(null);
      setHandle("");
      await load();
      if (res.enriched) {
        setEnrichedNote(true);
        await onChanged();
      }
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  /* THE OAUTH PATH: three steps and one browser.

     openAuthSessionAsync(authorizeUrl, returnUrl) opens the consent screen in
     a system browser, WATCHES for a redirect to returnUrl, closes the browser
     itself and resolves with the final URL. That last part is why nothing in
     navigation/RootNavigator.tsx changes: the answer arrives as the resolved
     value of this promise, not as a deep link delivered to the app, so the
     NavigationContainer needs no `linking` prop and there is no route to
     register for it. Adding one would be a second way into this state with
     nothing keeping the two in step.

     THE RETURN URL IS THE LITERAL kolabo:// SCHEME, built by oauthReturnUrl
     rather than by Linking.createURL. lib/socialConnect.ts argues that at
     length; the short version is that createURL yields an exp:// URL under
     Expo Go, the backend allowlist discards it without refusing it, and the
     creator is stranded on raw JSON. THE COST IS THAT THIS NEEDS A
     DEVELOPMENT BUILD, since only a build that declares the scheme registers
     it with the operating system. lib/googleSignIn.ts already carries the
     same constraint, so it asks nothing new of the pilot. */
  async function connect() {
    if (!adding || !adding.canConnect) return;
    const platform = adding;
    setConnecting(platform.id);
    setError(null);
    setConnectedNote(null);
    const returnUrl = oauthReturnUrl(platform.id);
    try {
      const { authorize_url } = await api<{ authorize_url: string }>(
        `/profiles/oauth/${platform.id}/start`,
        { method: "POST", token, body: { redirect_to: returnUrl } }
      );
      const result = await WebBrowser.openAuthSessionAsync(authorize_url, returnUrl);
      /* "dismiss" is the creator closing the sheet, "cancel" is the system
         closing it for them, and NEITHER IS AN ERROR. Backing out of a
         consent screen is an ordinary thing to do. Answering it with a red
         banner tells somebody who simply changed their mind that they broke
         something, so the section is left exactly as they found it. */
      if (result.type !== "success") return;

      const { connected: platformBack, socialError } = readCallbackParams(result.url);
      if (socialError) {
        /* AN EXISTING BACKEND CODE, so errorMessages.ts already holds a
           French and an English sentence for it and no new copy is written
           for it here. It is also the only value off this URL that reaches a
           screen, and it reaches one through a catalogue lookup that falls
           back to the generic sentence, so a code somebody made up cannot put
           words of its own in front of a creator. */
        setError(errorText({ code: socialError }, t));
        return;
      }
      if (!platformBack) return;

      setAdding(null);
      setHandle("");
      /* RELOADED RATHER THAN PATCHED IN. The callback is where the backend
         writes the follower count, its PLATFORM_API provenance and the real
         handle in place of the numeric id, and none of that is in anything
         this function is holding. The list is the only place those values
         exist. */
      await load();
      setConnectedNote(t("profile.socialConnected", { platform: platform.label }));
      await onChanged();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setConnecting(null);
    }
  }

  async function remove(id: string) {
    try {
      await api(`/profiles/${userId}/social-accounts/${id}`, { method: "DELETE", token });
    } catch {
      // ignore; the list reload below reflects the true state
    }
    void load();
  }

  return (
    <View>
      <SectionTitle>{t("profile.socialTitle")}</SectionTitle>
      <Hint>{t("profile.socialSub")}</Hint>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {enrichedNote ? <Banner kind="success">{t("profile.enriched")}</Banner> : null}
      {connectedNote ? <Banner kind="success">{connectedNote}</Banner> : null}

      {accounts.length === 0 ? (
        <Hint>{t("profile.socialEmpty")}</Hint>
      ) : (
        <View style={{ gap: space(2), marginTop: space(2) }}>
          {accounts.map((a) => (
            <View key={a.id} style={styles.row}>
              <View style={{ flexShrink: 1 }}>
                <Text style={styles.rowTitle}>{PLATFORM_LABELS[a.platform] ?? a.platform}</Text>
                <Text style={styles.rowSub}>
                  @{a.handle}
                  {a.follower_count !== null && a.follower_count !== undefined
                    ? ` · ${a.follower_count.toLocaleString()}`
                    : ""}
                </Text>
              </View>
              <View style={{ flexDirection: "row", alignItems: "center", gap: space(2) }}>
                <Text style={[styles.chip, a.status === "verified" ? styles.chipOk : styles.chipMuted]}>
                  {a.status === "verified" ? t("profile.verified") : t("profile.pending")}
                </Text>
                <Text style={styles.remove} onPress={() => remove(a.id)}>
                  {t("profile.remove")}
                </Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {adding ? (
        <View style={{ marginTop: space(3) }}>
          {adding.canConnect ? (
            <View style={{ marginBottom: space(4) }}>
              <Button
                title={t("profile.socialConnectCta", { platform: adding.label })}
                onPress={connect}
                loading={connecting === adding.id}
                disabled={connecting !== null}
              />
              <Hint>{t("profile.socialConnectHint", { platform: adding.label })}</Hint>
            </View>
          ) : null}
          <Field
            label={t("profile.handleFor", { platform: adding.label })}
            value={handle}
            onChangeText={(v) => setHandle(v.replace(/^@/, ""))}
            autoCapitalize="none"
            placeholder={adding.prefix}
          />
          {!platformHasAudience(adding.id) ? <Hint>{t("profile.noAudienceHint")}</Hint> : null}
          <View style={{ flexDirection: "row", gap: space(2), marginTop: space(2) }}>
            <View style={{ flex: 1 }}>
              <PrimaryButton
                title={busy ? t("common.working") : t("profile.addToProfile")}
                onPress={add}
                loading={busy}
                disabled={!handle.trim()}
              />
            </View>
            <View style={{ flex: 1 }}>
              <GhostButton
                title={t("common.cancel")}
                onPress={() => {
                  setAdding(null);
                  setHandle("");
                }}
              />
            </View>
          </View>
        </View>
      ) : (
        <View style={{ marginTop: space(3) }}>
          <Text style={styles.addLabel}>{t("profile.socialAdd")}</Text>
          <View style={styles.tiles}>
            {SOCIAL_PLATFORMS.map((p) => {
              const on = connected.has(p.id);
              return (
                <Pressable
                  key={p.id}
                  disabled={on}
                  onPress={() => {
                    setAdding(p);
                    setHandle("");
                    setError(null);
                    setConnectedNote(null);
                  }}
                  style={[styles.tile, on && styles.tileOn]}
                >
                  <Text style={[styles.tileText, on && styles.tileTextOn]}>{p.label}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
    gap: space(2),
  },
  rowTitle: { fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink },
  rowSub: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 2 },
  chip: { fontSize: font.tiny, fontFamily: family.bodySemi, overflow: "hidden", borderRadius: radius.pill, paddingHorizontal: space(2), paddingVertical: 3 },
  chipOk: { backgroundColor: "#e7f6f0", color: colors.success },
  chipMuted: { backgroundColor: colors.surface2, color: colors.muted },
  remove: { fontSize: font.small, color: colors.danger, fontFamily: family.bodySemi },
  addLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(2) },
  tiles: { flexDirection: "row", flexWrap: "wrap", gap: space(2) },
  tile: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    paddingHorizontal: space(3),
    paddingVertical: space(2.5),
    minWidth: 96,
    alignItems: "center",
  },
  tileOn: { borderColor: colors.teal, backgroundColor: colors.tealSoft },
  tileText: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink },
  tileTextOn: { color: colors.teal600 },
});
