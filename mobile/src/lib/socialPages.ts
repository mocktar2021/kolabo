import { platformCanConnect } from "./socialPlatforms";

/* Which Page a connected account is actually selling, and when to ask.

   PURE, AND IN lib/ RATHER THAN IN THE COMPONENT, for the same reason
   socialConnect.ts is: the half that decides WHETHER to offer the question is
   the half that fails silently. Get it wrong one way and a creator with four
   Facebook Pages is left staring at a numeric id with nothing on screen to
   explain it, which is the defect this whole feature exists to fix. Get it
   wrong the other way and every creator is nagged to choose a Page they have
   already got a verified number for. Neither throws, neither logs, and both
   read as "the app is a bit odd". Here it is an object in and a boolean out,
   so tests/socialPages.test.ts can hold every case without a handset.

   NOTHING HERE IMPORTS FROM react-native, deliberately, exactly as
   socialConnect.ts does not: vitest runs in a node environment (see
   vitest.config.ts) and an RN import would make the test suite need a
   renderer to answer a question about two fields. */

/* One Page a creator manages, mirrored from schemas.SocialPageOut.

   `name` AND `follower_count` ARE BOTH NULLABLE and the type says so rather
   than wishing otherwise. The backend passes on what the platform stated and
   invents nothing, so a Page the platform named no audience for arrives with
   a null, and a client that rendered that as 0 would be publishing a figure
   nobody reported. `id` is the only field that ever goes back, and
   oauth_service.select_page treats it as untrusted when it does. */
export type SocialPage = {
  id: string;
  name: string | null;
  follower_count: number | null;
};

/* The three fields of a connected account this question is asked about.

   A STRUCTURAL SHAPE RATHER THAN profileTypes.SocialAccount, so the rule can
   be exercised against a two-line literal in a test instead of against a full
   account row, and so this module has nothing to say about the fields it does
   not read. */
export type PageChoiceAccount = {
  platform: string;
  method: string;
  follower_count?: number | null;
};

/* Whether to offer this account's owner the "choose your Page" question.

   THREE CONDITIONS, AND EACH ONE RULES OUT A DIFFERENT WRONG PROMPT.

   `method` MUST BE "oauth". A handle somebody typed has no token behind it,
   so there is no Page list to read and the endpoint would answer
   oauth_token_expired. Asking would be offering a door with nothing behind
   it.

   THE PLATFORM MUST HAVE A PROVIDER. platformCanConnect mirrors
   oauth.build_default_providers, and a platform without one answers
   oauth_platform_unsupported. Today that means Facebook and nothing else.

   THERE MUST BE NO FOLLOWER COUNT, which is the condition that carries the
   actual meaning. A count on an oauth account was written by
   _write_audience, and _write_audience only ever ran because
   MetaOAuthProvider.read_audience found EXACTLY ONE Page. So a count present
   is the platform having already answered this question unambiguously, and a
   count absent is the ambiguity itself, showing on screen as a numeric
   app-scoped id and a blank where a number belongs.

   ZERO IS A COUNT, not an absence, and the comparison is written against null
   and undefined rather than as a falsy test for exactly that reason. A Page
   the platform reported zero followers for has been chosen and reported; a
   `!account.follower_count` here would ask its owner to choose it again, for
   ever. */
export function needsPageChoice(account: PageChoiceAccount): boolean {
  if (account.method !== "oauth") return false;
  if (!platformCanConnect(account.platform)) return false;
  return account.follower_count === null || account.follower_count === undefined;
}

/* A follower count as this app writes one, or null when there is none.

   toLocaleString WITH THE READER'S LANGUAGE, which is what every other
   audience and money figure in the app already does (DiscoverScreen,
   CreatorPublicScreen, ProposalThread). Grouping is not decoration on a
   number a brand is about to spend against: 1688 and 16880 are one glance
   apart without it.

   NULL RATHER THAN AN EMPTY STRING, so a caller has to decide what to show
   instead and cannot accidentally render a blank where a number was promised.

   A NON-NUMBER ANSWERS NULL TOO. The value comes off a JSON body, so the type
   above is a claim rather than a guarantee, and NaN is the one thing worse
   than no number: it looks like a bug in the platform rather than in us. */
export function followerText(count: number | null | undefined, language: string): string | null {
  if (typeof count !== "number" || !Number.isFinite(count)) return null;
  return count.toLocaleString(language);
}
