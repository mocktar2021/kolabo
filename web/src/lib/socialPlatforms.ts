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
};

export const SOCIAL_PLATFORMS: SocialPlatform[] = [
  { id: "instagram", label: "Instagram", prefix: "instagram.com/", hasAudience: true },
  { id: "tiktok", label: "TikTok", prefix: "tiktok.com/@", hasAudience: true },
  { id: "youtube", label: "YouTube", prefix: "youtube.com/@", hasAudience: true },
  { id: "facebook", label: "Facebook", prefix: "facebook.com/", hasAudience: true },
  { id: "x", label: "X", prefix: "x.com/", hasAudience: true },
  { id: "snapchat", label: "Snapchat", prefix: "snapchat.com/add/", hasAudience: true },
  { id: "linkedin", label: "LinkedIn", prefix: "linkedin.com/in/", hasAudience: true },
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
  { id: "whatsapp", label: "WhatsApp", prefix: "wa.me/", hasAudience: false }
];

/* Whether a follower count is a thing that can honestly be asked for on this
   platform. Unknown ids answer true: this is a UI question about which input
   to render, and hiding the field for a platform we simply do not recognise
   would silently drop data a creator meant to give us. */
export function platformHasAudience(platformId: string): boolean {
  return SOCIAL_PLATFORMS.find((p) => p.id === platformId)?.hasAudience ?? true;
}

/* The platforms a creator can connect by authorising Kolabo ON the platform,
   instead of by typing a handle into the box.

   THIS IS A COPY OF oauth.build_default_providers() IN THE BACKEND, AND
   NOTHING ENFORCES THAT IT STAYS ONE. There is no endpoint that reports which
   platforms have a provider, so this list is a decision made in
   backend/app/modules/profiles/oauth.py and written down again here by hand.
   It is a constant rather than something inferred precisely so that the
   coupling is visible: a reader can see what it has to agree with.

   The two ways it can drift are not equally loud, which is why they are worth
   naming:

     a platform listed here that the backend has no provider for shows a
     Connect button whose POST answers `oauth_platform_unsupported`. The
     creator reads that as a broken button, but somebody does at least find
     out;

     a platform the backend HAS a provider for and that is missing here shows
     no Connect button at all. Nothing fails, nothing is logged, and the
     feature is simply invisible. This is the direction that goes unnoticed,
     and it is the one to check when a provider is added.

   FACEBOOK ALONE TODAY. build_default_providers registers MetaOAuthProvider
   and nothing else, and registers even that only where the deployment carries
   both a Meta app id and a secret. A deployment with neither is the first
   kind of drift above, but it is a configuration question rather than a code
   one: the button is right, the server is not set up. */
export const CONNECTABLE_PLATFORMS: string[] = ["facebook"];

/* Whether to offer the Connect action for a platform. Unknown ids answer
   false, which is the opposite of platformHasAudience above and is the right
   default for the opposite reason: that one decides whether to collect
   something and guesses generously, this one decides whether to send somebody
   on a handshake, and a handshake we have no provider for cannot succeed. */
export function canConnect(platformId: string): boolean {
  return CONNECTABLE_PLATFORMS.includes(platformId);
}
