import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { readConnectResult } from "../../lib/socialConnect";
import {
  SOCIAL_PLATFORMS,
  canConnect,
  platformHasAudience,
  type SocialPlatform,
} from "../../lib/socialPlatforms";
import { PLATFORM_LABELS } from "../../lib/platforms";
import type { SocialAccount } from "../../lib/profileTypes";
import { Banner, Field, GhostButton, Hint, PrimaryButton, SectionTitle } from "../ui";
import { colors, family, font, radius, space } from "../../theme";

/* Connected accounts, plus the two ways to add one.

   TYPING A HANDLE goes in as a manual proof and stays PENDING until an admin
   looks at it. It is still the only route for every platform except Facebook,
   and it stays on screen for Facebook too: a creator who opens the consent
   screen and decides against granting permissions has to be able to carry on.
   If the connect response says it enriched, the parent reloads so the
   auto-filled profile fields show at once.

   AUTHORISING ON THE PLATFORM is the other, and only where canConnect says a
   provider exists. See connect() below for why it needs no deep link
   configuration. */
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
  /* The one-line answer the OAuth round trip comes back with. It carries its
     own tone because the two things it can say are not the same kind of news:
     a connection is a success, and backing out of a consent screen is not a
     failure and must not be dressed as one. */
  const [notice, setNotice] = useState<{ kind: "info" | "success"; text: string } | null>(null);

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

  /* Connecting by authorising Kolabo on the platform itself.

     openAuthSessionAsync IS WHAT MAKES THIS NEED NO DEEP LINK SETUP, and that
     is the whole reason it is used rather than Linking.openURL plus a
     listener. It opens the system authentication browser, WATCHES for a
     redirect to the returnUrl it was given, closes itself the moment one
     arrives, and hands the url straight back as its return value. Nothing is
     routed into the app, so there is no scheme handler to register beyond the
     one app.json already declares, no `linking` prop on the navigator, and no
     subscription to tear down. The whole handshake is this one await.

     THE RETURN URL COMES FROM Linking.createURL, which builds it from
     expo.scheme in app.json. That is already "kolabo", which is what makes
     this work at all: the backend allowlist accepts the configured web origin
     or anything under kolabo://, and refuses everything else SILENTLY. A
     refused value is not an error a creator sees, it is a creator who ends up
     looking at the callback's JSON inside the in-app browser while this await
     never resolves, until they close it by hand and land on the cancel branch
     below.

     THAT IS EXACTLY WHAT HAPPENS IN EXPO GO, and it is worth knowing before
     somebody tries it there. Launched from Expo Go, createURL answers an
     exp://... url rather than a kolabo:// one, which the allowlist refuses.
     This flow can only be exercised in a development or production build. */
  async function connect(platform: SocialPlatform) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const returnUrl = Linking.createURL("profile/social-connected");
      const { authorize_url } = await api<{ authorize_url: string }>(
        `/profiles/oauth/${platform.id}/start`,
        { method: "POST", token, body: { redirect_to: returnUrl } }
      );
      const outcome = await WebBrowser.openAuthSessionAsync(authorize_url, returnUrl);

      /* READ STRUCTURALLY, BY ASKING FOR THE url, rather than by comparing
         `type` against a string literal. Across expo-web-browser versions
         that field has been both a string union and a string ENUM, and under
         `strict` a string enum does not compare equal to a string literal at
         all: `outcome.type === "success"` is a type error on one of those
         spellings and silently fine on the other. Asking whether there is a
         url avoids the question, and it is also the question actually being
         asked, because the redirect result is the only variant that carries
         one. It narrows outcome.url for the parse below at the same time. */
      if (!("url" in outcome)) {
        const how = String(outcome.type);
        /* Backed out: closed the browser, or pressed the system Done button.
           An ordinary thing to do and the commonest non-success by a
           distance, so it is said quietly and never in red. */
        if (how === "cancel" || how === "dismiss") {
          setNotice({ kind: "info", text: t("profile.socialConnectCancelled") });
          return;
        }
        /* Anything else: "locked" today, and whatever a later SDK adds.
           Nothing is known about what happened, so nothing is claimed about
           it, and errorText answers a null with the generic sentence. */
        setError(errorText(null, t));
        return;
      }

      const marker = readConnectResult(outcome.url);
      if (marker === null) {
        /* A redirect to our own returnUrl that carries neither marker. It
           should not be reachable: the callback appends one or the other
           before it redirects at all. */
        setError(errorText(null, t));
        return;
      }
      if (marker.kind === "failed") {
        /* The backend's own code, so this reuses the sentence
           errorMessages.ts already holds for it in both languages. No failure
           copy is written for this feature. */
        setError(errorText({ code: marker.code }, t));
        return;
      }

      setNotice({ kind: "success", text: t("profile.socialConnected") });
      /* The list first, for the follower number the authorisation just
         earned, then the parent for the profile fields it may have filled in.
         Same order, and the same two calls, as the handle path above. */
      await load();
      await onChanged();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
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
      {notice ? <Banner kind={notice.kind}>{notice.text}</Banner> : null}
      {enrichedNote ? <Banner kind="success">{t("profile.enriched")}</Banner> : null}

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
          {/* Connect, for the platforms with a provider behind them. Above the
              tiles rather than inside one, because a tile opens the handle
              form and these are the alternative to it, not a variant of it.
              Only while the account is not already connected, which is the
              same condition that disables a tile. */}
          {SOCIAL_PLATFORMS.filter((p) => canConnect(p.id) && !connected.has(p.id)).map((p) => (
            <View key={p.id} style={{ marginBottom: space(3) }}>
              <PrimaryButton
                title={busy ? t("common.working") : t("profile.socialConnect", { platform: p.label })}
                onPress={() => connect(p)}
                loading={busy}
              />
            </View>
          ))}
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
