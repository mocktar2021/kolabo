/* Platforms a creator can CONNECT an account on, mirrored from
   web/src/lib/socialPlatforms.ts. Narrower than SELLABLE_PLATFORMS (UGC is
   sellable but not connectable). `prefix` is shown before the handle input;
   `hasAudience` mirrors PLATFORMS_WITH_AUDIENCE in the backend and decides
   whether a follower-count field is offered — a guessed number on a card a
   brand shortlists from is worse than no number.

   `canConnect` answers a different question: is there an OAuth provider
   behind this platform, so that a Connect button can be offered instead of a
   handle to type? It MIRRORS oauth.build_default_providers in
   backend/app/modules/profiles/oauth.py, by hand, and nothing checks the two
   against each other. It will therefore drift, and the drift is quiet in both
   directions: a false here hides a button that would have worked, and a true
   here offers one that answers oauth_platform_unsupported. Today the registry
   builds exactly one provider, Meta, so facebook is the only true value.

   FALSE IS NOT "NOT SUPPORTED", it is "not automatically". Every platform on
   this list can still be claimed by typing a handle, which is the path that
   was here first and the only one seven of these eight have. */
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
  { id: "whatsapp", label: "WhatsApp", prefix: "wa.me/", hasAudience: false, canConnect: false },
];

export function platformHasAudience(platformId: string): boolean {
  return SOCIAL_PLATFORMS.find((p) => p.id === platformId)?.hasAudience ?? true;
}

/* Whether this platform has an OAuth provider behind it, and therefore
   whether an account on it can have arrived by handshake rather than by
   somebody typing a handle. Reads the same `canConnect` flag the tiles read,
   so the Connect button and everything that follows a connection cannot
   disagree about which platforms the handshake covers.

   AN UNKNOWN ID ANSWERS FALSE, which is the opposite default to
   platformHasAudience above and is deliberate. There, "we do not recognise
   this" must not hide a field a creator may legitimately fill. Here it would
   offer somebody a Page picker on a platform with no provider to ask, and
   that sheet could only ever come back empty. */
export function platformCanConnect(platformId: string): boolean {
  return SOCIAL_PLATFORMS.find((p) => p.id === platformId)?.canConnect ?? false;
}
