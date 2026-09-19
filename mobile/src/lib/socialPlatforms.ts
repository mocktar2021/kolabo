/* Platforms a creator can CONNECT an account on, mirrored from
   web/src/lib/socialPlatforms.ts. Narrower than SELLABLE_PLATFORMS (UGC is
   sellable but not connectable). `prefix` is shown before the handle input;
   `hasAudience` mirrors PLATFORMS_WITH_AUDIENCE in the backend and decides
   whether a follower-count field is offered — a guessed number on a card a
   brand shortlists from is worse than no number. */
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
  { id: "whatsapp", label: "WhatsApp", prefix: "wa.me/", hasAudience: false },
];

export function platformHasAudience(platformId: string): boolean {
  return SOCIAL_PLATFORMS.find((p) => p.id === platformId)?.hasAudience ?? true;
}

/* The platforms a creator can connect by authorising Kolabo ON the platform,
   instead of by typing a handle. Mirrored from web/src/lib/socialPlatforms.ts,
   and through it from oauth.build_default_providers() in the backend.

   NOTHING ENFORCES THAT THIS STAYS IN STEP WITH build_default_providers.
   There is no endpoint reporting which platforms have a provider, so this is
   a hand-kept copy of a decision made in
   backend/app/modules/profiles/oauth.py. A platform listed here with no
   provider behind it shows a button that answers
   `oauth_platform_unsupported`; a platform with a provider and no entry here
   shows no button at all, which is the quiet direction and the one to check
   when a provider is added. Facebook alone today. */
export const CONNECTABLE_PLATFORMS: string[] = ["facebook"];

/* Unknown ids answer false, unlike platformHasAudience above: that one
   decides whether to collect something and guesses generously, this one
   decides whether to send somebody on a handshake that cannot succeed
   without a provider. */
export function canConnect(platformId: string): boolean {
  return CONNECTABLE_PLATFORMS.includes(platformId);
}
