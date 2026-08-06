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
