/* Platforms a creator can CONNECT an account on, with the URL prefix shown in
   the handle modal. Narrower than SELLABLE_PLATFORMS in lib/platforms.ts,
   which is everything a creator can price: UGC is made for the brand to run
   as its own ad and is never posted on the creator's account, so it is
   sellable and not connectable.

   Order matches how creators in the pilot markets rank them, except for the
   last entry — see the note on it.

   hasAudience mirrors PLATFORMS_WITH_AUDIENCE in backend/app/core/platforms.py
   and answers one question: does this platform publish a follower number we
   could display and, in time, verify? Where it is false the profile form does
   not ask for one, because a field somebody fills in with a guess is worse
   than a field that is not there — an unverifiable number on a creator's card
   is exactly the kind of figure a brand shortlists on and then discovers was
   invented. */
export type SocialPlatform = {
  id: string;
  label: string;
  prefix: string;
  hasAudience: boolean;
  canConnect: boolean;
};

export const SOCIAL_PLATFORMS: SocialPlatform[] = [
  { id: "instagram", label: "Instagram", prefix: "instagram.com/", hasAudience: true, canConnect: false },
  { id: "tiktok", label: "TikTok", prefix: "tiktok.com/@", hasAudience: true, canConnect: false },
  { id: "youtube", label: "YouTube", prefix: "youtube.com/@", hasAudience: true, canConnect: false },
  { id: "facebook", label: "Facebook", prefix: "facebook.com/", hasAudience: true, canConnect: true },
  { id: "x", label: "X", prefix: "x.com/", hasAudience: true, canConnect: false },
  { id: "snapchat", label: "Snapchat", prefix: "snapchat.com/add/", hasAudience: true, canConnect: false },
  { id: "linkedin", label: "LinkedIn", prefix: "linkedin.com/in/", hasAudience: true, canConnect: false },
  /* WhatsApp, and it was missing from this list while the backend has
     accepted it the whole time: "whatsapp" is in PLATFORM_DELIVERABLES with a
     Status deliverable, so a creator could be sold against it and could not
     say they were on it.

     The prefix is wa.me/, which takes the phone number in international form
     without the + — that is the link WhatsApp itself hands out, and it is what
     a creator will paste.

     hasAudience is false and that is the interesting half. WhatsApp Status
     publishes no public metric: there is no follower count to read, nothing to
     verify against later, and no number a brand could compare with anybody
     else's. So the profile form does not ask for one and the audience chip —
     which has always been conditional on a non-null count — renders nothing
     rather than a blank or a zero.

     Last in the list because it is the newest entry and not because it is the
     least used; we have no ranking data for it in the pilot markets, and
     inventing a position for it would be inventing the one thing this order
     is supposed to encode. */
  { id: "whatsapp", label: "WhatsApp", prefix: "wa.me/", hasAudience: false, canConnect: false }
];

/* Whether a follower count is a thing that can honestly be asked for on this
   platform. Unknown ids answer true: this is a UI question about which input
   to render, and hiding the field for a platform we simply do not recognise
   would silently drop data a creator meant to give us. */
export function platformHasAudience(platformId: string): boolean {
  return SOCIAL_PLATFORMS.find((p) => p.id === platformId)?.hasAudience ?? true;
}

/* THIS MIRRORS THE BACKEND'S PROVIDER REGISTRY, AND NOTHING ENFORCES THAT.

   canConnect answers one question: is there an OAuth provider on the server
   that POST /profiles/oauth/{platform}/start can hand back an authorize_url
   for? Exactly one platform answers yes today, because
   oauth.build_default_providers in backend/app/modules/profiles/oauth.py
   registers exactly one provider, MetaOAuthProvider, whose `platform` is
   "facebook". Every other id here would get `oauth_platform_unsupported`, so
   a Connect button on one of them is a button whose only possible outcome is
   a refusal.

   THE DRIFT IS REAL AND IT RUNS ONE WAY. The day TikTok's Login Kit is
   approved and a second provider is registered on the server, nothing in this
   repository fails: the web app goes on not offering the button, and a
   working backend feature has no way in. Nothing in CI can catch it either,
   because this file has no way to read a Python dict. The fix is not a
   sharper comment, it is a server endpoint that lists the configured
   providers, which this list would then be replaced by rather than kept in
   step with.

   The other direction is safe, which is why a literal is worth shipping in
   the meantime: a true here for a platform the server has no provider for
   ends in `oauth_platform_unsupported`, a code both catalogues already
   translate, so the worst case is a creator reading a sentence that says the
   button does not work yet. */
export const CONNECTABLE_PLATFORMS: SocialPlatform[] = SOCIAL_PLATFORMS.filter((p) => p.canConnect);
