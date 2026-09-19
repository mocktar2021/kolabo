import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import * as WebBrowser from "expo-web-browser";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { SOCIAL_PLATFORMS, platformHasAudience, type SocialPlatform } from "../../lib/socialPlatforms";
import { oauthReturnUrl, readCallbackParams } from "../../lib/socialConnect";
import { followerText, needsPageChoice, type SocialPage } from "../../lib/socialPages";
import { followerNote, socialStatusChip } from "../../lib/socialStatus";
import { PLATFORM_LABELS } from "../../lib/platforms";
import type { SocialAccount } from "../../lib/profileTypes";
import {
  Banner,
  Button,
  ChoiceSheet,
  Field,
  GhostButton,
  Hint,
  PrimaryButton,
  SectionTitle,
  type Choice,
} from "../ui";
import { colors, family, font, radius, space } from "../../theme";
/* Imported for its side effect, the way PackagesSection imports
   packageStrings: the module registers the profile.socialConnect* and
   profile.socialPage* keys on i18n, and without this line every one of them
   renders as its own key. */
import "../../lib/socialConnectStrings";

/* The state chip on one row: four states now, not two.

   A COMPONENT RATHER THAN THE TERNARY THAT USED TO SIT HERE. That ternary
   asked one question, "is this verified", and answered everything else with
   the pending chip, so a creator who had signed in to Facebook, granted the
   permissions and chosen their Page was shown the same badge as somebody who
   had typed a name into a box, and an account an admin had REFUSED was shown
   it too. Which chip goes with which state lives in lib/socialStatus so the
   public page reads the same rule. */
function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation();
  const chip = socialStatusChip(status);
  const tone = {
    strong: styles.chipStrong,
    quiet: styles.chipQuiet,
    neutral: styles.chipMuted,
    bad: styles.chipBad,
  }[chip.tone];
  return <Text style={[styles.chip, tone]}>{t(chip.key)}</Text>;
}

/* Where the number on the line above came from, or nothing at all.

   THE CREATOR IS SHOWN THIS TOO, not only the brand, and that is deliberate:
   the person best placed to notice that a figure is still their own word is
   the person who typed it, and the fix for it is the Connect button two
   sections down. followerNote decides what may be claimed, including that a
   row from before the provenance columns existed claims nothing. */
function SourceLine({ account }: { account: SocialAccount }) {
  const { t, i18n } = useTranslation();
  const note = followerNote(account, i18n.language);
  if (!note) return null;
  return (
    <Text style={[styles.rowSource, note.checked ? styles.rowSourceChecked : null]}>
      {t(note.key, {
        platform: PLATFORM_LABELS[account.platform] ?? account.platform,
        date: note.date,
      })}
    </Text>
  );
}

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

   CHOOSE YOUR PAGE is the third thing this section does, and it is here
   because a Facebook connection can succeed completely and still leave a row
   with nothing readable on it. oauth.MetaOAuthProvider.read_audience records
   a follower count only where the creator manages EXACTLY ONE Page, because
   with four of them any pick would publish a number the creator never chose,
   on the one figure a brand reads before it spends. So a creator who
   administers four Pages gets a row showing the numeric app-scoped id the
   token exchange returned, no count, and until now no explanation of any
   kind. The action on the row asks them which Page they sell on, and
   oauth_service.select_page writes the answer through the same
   _write_audience the one-Page path uses, so the two cannot record different
   things.

   A CREATOR WITH ONE PAGE NEVER SEES ANY OF IT: their count was filled in at
   connect time, and needsPageChoice reads exactly that. A creator with none
   gets the sheet's empty sentence rather than an empty sheet.

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
  const { t, i18n } = useTranslation();
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
  /* The account whose Page sheet is open, or null. The ACCOUNT rather than a
     boolean, because choosing has to post to the platform the sheet was
     opened from and the row it came out of is gone from the closure by the
     time the answer lands. */
  const [picking, setPicking] = useState<SocialAccount | null>(null);
  const [pages, setPages] = useState<SocialPage[]>([]);
  /* The account whose Page list is in flight, so the waiting sits on the row
     that was tapped rather than on the whole section. */
  const [loadingPagesFor, setLoadingPagesFor] = useState<string | null>(null);
  const [pageNote, setPageNote] = useState<string | null>(null);

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

  /* The sheet's rows, built from what the platform said a moment ago rather
     than from anything stored. A Page the platform named no audience for says
     so on its second line instead of showing a zero it never earned, which is
     the same rule SocialAccountOut keeps about a null count. */
  const pageOptions: Choice[] = pages.map((p) => {
    const followers = followerText(p.follower_count, i18n.language);
    return {
      value: p.id,
      label: p.name || t("profile.socialPageUnnamed"),
      description: followers
        ? t("profile.socialPageFollowers", { followers })
        : t("profile.socialPageFollowersUnknown"),
    };
  });

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

  /* THE LIST IS FETCHED BEFORE THE SHEET OPENS, not while it is open. A sheet
     that has not answered yet and a sheet for a creator with no Pages look
     identical, and only one of those two is telling the truth. Fetching first
     means the sheet only ever opens onto a settled answer, and the row
     carries the waiting.

     NOTHING IS CACHED BETWEEN OPENINGS. oauth_service._own_pages re-reads the
     list on BOTH of its endpoints, deliberately, so that a Page somebody lost
     access to yesterday is not selectable today. Holding a copy on this side
     would put the screen back out of step with the only check that matters. */
  async function openPages(account: SocialAccount) {
    if (loadingPagesFor !== null) return;
    setLoadingPagesFor(account.id);
    setError(null);
    setPageNote(null);
    try {
      const list = await api<SocialPage[]>(`/profiles/oauth/${account.platform}/pages`, { token });
      setPages(list);
      setPicking(account);
    } catch (e) {
      /* oauth_token_expired for an account with no stored credentials and
         oauth_exchange_failed for a Graph that could not be reached are both
         backend codes, so errorText finds their French and English sentences
         in errorMessages.ts and no copy is written for them here. */
      setError(errorText(e, t));
    } finally {
      setLoadingPagesFor(null);
    }
  }

  /* RELOADED RATHER THAN PATCHED IN, for the reason connect() reloads. The
     select endpoint does answer with the updated account, but the list is the
     only place the row on screen reads from, and filling one row from a
     response while its neighbours come from a fetch is how the two drift.

     The id is encoded on the way into the path because it is a platform's
     string and nothing here is entitled to assume what is in it. The backend
     does not trust it either: select_page re-reads the creator's own Page
     list and writes only a Page that appears in it, which is what makes
     oauth_page_not_found a refusal rather than a stamp on somebody else's
     audience. */
  async function choosePage(pageId: string) {
    const account = picking;
    if (!account) return;
    setPicking(null);
    setLoadingPagesFor(account.id);
    setError(null);
    const label = PLATFORM_LABELS[account.platform] ?? account.platform;
    try {
      await api<SocialAccount>(
        `/profiles/oauth/${account.platform}/pages/${encodeURIComponent(pageId)}`,
        { method: "POST", token }
      );
      await load();
      setPageNote(t("profile.socialPageChosen", { platform: label }));
      await onChanged();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setLoadingPagesFor(null);
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
      {pageNote ? <Banner kind="success">{pageNote}</Banner> : null}

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
                    ? ` · ${a.follower_count.toLocaleString(i18n.language)}`
                    : ""}
                </Text>
                <SourceLine account={a} />
                {needsPageChoice(a) ? (
                  <>
                    <Text style={styles.rowWhy}>
                      {t("profile.socialPageWhy", {
                        platform: PLATFORM_LABELS[a.platform] ?? a.platform,
                      })}
                    </Text>
                    <Text
                      style={styles.choosePage}
                      onPress={() => void openPages(a)}
                      accessibilityRole="button"
                    >
                      {loadingPagesFor === a.id
                        ? t("common.working")
                        : t("profile.socialPageChoose")}
                    </Text>
                  </>
                ) : null}
              </View>
              <View style={{ flexDirection: "row", alignItems: "center", gap: space(2) }}>
                <StatusChip status={a.status} />
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
                    setPageNote(null);
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

      {/* One sheet for the whole section rather than one per row. Only one
          can be open at a time by construction, and `picking` is the row it
          belongs to. */}
      <ChoiceSheet
        open={picking !== null}
        title={t("profile.socialPageTitle")}
        options={pageOptions}
        empty={
          picking
            ? t("profile.socialPageNone", {
                platform: PLATFORM_LABELS[picking.platform] ?? picking.platform,
              })
            : ""
        }
        onChange={(pageId) => void choosePage(pageId)}
        onClose={() => setPicking(null)}
      />
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
  rowSource: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 2, lineHeight: 16 },
  /* The checked figure is the only one that gets colour. A marker that looks
     the same as the sentence beside it is not a marker. */
  rowSourceChecked: { fontFamily: family.bodySemi, color: colors.success },
  rowWhy: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: space(1.5), lineHeight: 17 },
  choosePage: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.indigo, marginTop: space(1.5) },
  chip: { fontSize: font.tiny, fontFamily: family.bodySemi, overflow: "hidden", borderRadius: radius.pill, paddingHorizontal: space(2), paddingVertical: 3 },
  /* One style per tone in lib/socialStatus, and the distance between them is
     the message. chipStrong is an identity document an admin read.
     chipQuiet is the platform answering about its own account: real, and
     deliberately not dressed as the first. */
  chipStrong: { backgroundColor: "#e7f6f0", color: colors.success },
  chipQuiet: { backgroundColor: colors.surface, color: colors.indigo },
  chipMuted: { backgroundColor: colors.surface2, color: colors.muted },
  chipBad: { backgroundColor: "#fbeaea", color: colors.danger },
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
