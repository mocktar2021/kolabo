import { formatDate } from "./dates";

/* What a social account's state is allowed to claim, and where its follower
   number came from.

   PURE, AND IN lib/ RATHER THAN IN EITHER COMPONENT, for the reason
   socialPages.ts is: two screens render these two facts now, the creator's
   own profile and the public page a brand reads before it spends, and a rule
   written out twice is a rule that will eventually disagree with itself.
   Both failures here are silent. Badge a connected account as pending and
   the creator who actually authorised the platform is shown the same chip as
   somebody who typed a name into a box. Badge it as verified and a brand is
   told an identity document was checked when none was. Neither throws,
   neither logs, and both are read as a number on a page.

   NOTHING HERE IMPORTS FROM react-native, deliberately, exactly as
   socialPages.ts does not: vitest runs in a node environment (see
   vitest.config.ts) and an RN import would make the suite need a renderer to
   answer a question about three fields. lib/dates.ts is imported because it
   is the same kind of module and because a date library is not worth adding
   for one line of output. */

/* The four values backend profiles.models writes to social_accounts.status,
   named once rather than compared as loose literals at four call sites. */
export const PENDING = "pending";
export const CONNECTED = "connected";
export const VERIFIED = "verified";
export const REJECTED = "rejected";

/* The two values backend profiles.models writes to follower_source. A third
   possibility, null, is an absence rather than a value: see followerNote. */
export const SELF_REPORTED = "self_reported";
export const PLATFORM_API = "platform_api";

/* How loudly a chip is allowed to speak.

   strong   an admin read a real identity document. The only tone that may
            look like a promise about a PERSON.
   quiet    the platform answered about its own account, on a token the
            creator issued. Real, proved, and deliberately calmer than
            strong, because proving control of a handle is a smaller claim.
   neutral  nothing has been checked.
   bad      an admin looked and refused. */
export type SocialStatusTone = "strong" | "quiet" | "neutral" | "bad";

export type SocialStatusChip = { key: string; tone: SocialStatusTone };

/* The chip for one account's status.

   PENDING AND VERIFIED KEEP THE KEYS THEY ALREADY HAD in src/strings.ts.
   Writing a second translation of the same two words into the socialConnect
   bundle would put two versions of one label in the app with nothing to say
   which is current, which is the rule that bundle's own header states about
   error sentences. Only the two states that had no copy at all get new keys.

   AN UNKNOWN STATUS FALLS BACK TO PENDING, never to connected and never to
   verified. A value this build has not heard of can only come from a backend
   newer than the app, and the safe direction there is to understate: a state
   shown as waiting that turns out to be better is a disappointment, and one
   shown as checked that turns out not to be is a lie a brand spent money
   on. */
export function socialStatusChip(status: string | null | undefined): SocialStatusChip {
  if (status === VERIFIED) return { key: "profile.verified", tone: "strong" };
  if (status === CONNECTED) return { key: "profile.socialStatusConnected", tone: "quiet" };
  if (status === REJECTED) return { key: "profile.socialStatusRejected", tone: "bad" };
  return { key: "profile.pending", tone: "neutral" };
}

/* The three fields the provenance line reads.

   A STRUCTURAL SHAPE RATHER THAN profileTypes.SocialAccount, the way
   socialPages.PageChoiceAccount is, so the rule can be exercised against a
   three line literal and so this module has nothing to say about the fields
   it does not read. */
export type FollowerProvenance = {
  follower_count?: number | null;
  follower_source?: string | null;
  follower_verified_at?: string | null;
};

/* A key to render under a follower number, the date already written in the
   reader's language, and whether the number was checked by anything. The
   caller styles the checked one differently; that is the whole point of
   carrying the flag rather than letting the screen re-read the column. */
export type FollowerNote = { key: string; date: string; checked: boolean };

/* WHERE THIS NUMBER CAME FROM, SAID ON BOTH SIDES.

   A count the platform stated carries a positive marker AND the date it was
   read. A count the creator typed says plainly that it is the creator's own
   figure. Marking one of the two and leaving the reader to infer the other
   is the defect this exists to end: a number somebody typed into a form
   rendered identically to one read back through that person's own OAuth
   token, on the page a brand reads before deciding what to spend.

   A NULL SOURCE GETS NO MARKER AT ALL, and that is a decision rather than an
   oversight. Every row written before backend #161 added the column has a
   null here, and what a null means is not "the creator typed it" but "we do
   not know": the column did not exist when the number was stored. Writing
   "the creator's own figure" over those rows would invent a fact about
   creators whose counts may well have been read from a platform, and writing
   the checked marker over them would be far worse. Saying nothing is the one
   thing true of all of them, the set shrinks to nothing as accounts are
   edited or reconnected, and it is the same rule
   schemas.SocialAccountOut states for a null: say nothing rather than
   assume. An unrecognised source value takes the same path, and for the same
   reason.

   NO COUNT MEANS NO NOTE, whatever the source column holds. A caption under
   a blank space describes nothing.

   THE COUNT IS CHECKED AS A NUMBER RATHER THAN FOR TRUTHINESS, because the
   value comes off a JSON body: zero is a figure a platform really does
   report, and a string or a NaN is a broken payload rather than an audience
   to caption. */
export function followerNote(
  account: FollowerProvenance,
  language: string
): FollowerNote | null {
  const count = account.follower_count;
  if (typeof count !== "number" || !Number.isFinite(count)) return null;
  if (account.follower_source === PLATFORM_API) {
    const date = formatDate(account.follower_verified_at, language);
    /* A platform source with no date should not reach here, because the
       backend writes the two together. If one ever does, the claim is still
       true and only the date is missing, so it is made undated rather than
       thrown away. */
    return date
      ? { key: "profile.socialFollowersChecked", date, checked: true }
      : { key: "profile.socialFollowersCheckedUndated", date: "", checked: true };
  }
  if (account.follower_source === SELF_REPORTED) {
    return { key: "profile.socialFollowersSelf", date: "", checked: false };
  }
  return null;
}
