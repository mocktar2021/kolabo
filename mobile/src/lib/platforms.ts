/* Mirror of web/src/lib/platforms.ts and the backend platform map
   (backend/app/core/platforms.py). A deliverable is only offered where it
   actually exists, so a package the API would reject with a 400 cannot be
   built in the form. */
export const PLATFORM_DELIVERABLES: Record<string, string[]> = {
  instagram: ["reel", "post", "story", "carousel", "live"],
  tiktok: ["video", "photo_post", "story", "live"],
  facebook: ["reel", "post", "story", "live"],
  youtube: ["video", "short", "live", "community_post"],
  snapchat: ["snap", "story", "spotlight"],
  x: ["post", "thread", "video"],
  threads: ["post", "video"],
  linkedin: ["post", "article", "video"],
  whatsapp: ["status"],
  discord: ["server_post"],
  ugc: ["ugc_video", "ugc_photo"],
};

/* Everything a creator can price. Wider than the connectable social list: UGC
   is made for the brand to run as its own ad and is never posted on the
   creator's account, so it is sellable but not connectable. */
export const SELLABLE_PLATFORMS: { id: string; label: string }[] = [
  { id: "instagram", label: "Instagram" },
  { id: "tiktok", label: "TikTok" },
  { id: "youtube", label: "YouTube" },
  { id: "facebook", label: "Facebook" },
  { id: "snapchat", label: "Snapchat" },
  { id: "x", label: "X" },
  { id: "threads", label: "Threads" },
  { id: "linkedin", label: "LinkedIn" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "discord", label: "Discord" },
  { id: "ugc", label: "UGC" },
];

export const PLATFORM_LABELS: Record<string, string> = Object.fromEntries(
  SELLABLE_PLATFORMS.map((p) => [p.id, p.label])
);

export function deliverablesFor(platform: string): string[] {
  return PLATFORM_DELIVERABLES[platform] ?? [];
}

/* A readable label for a deliverable type id. The web app localises these via
   i18n (deliverable.<id>); here we prettify the id — "photo_post" -> "Photo
   post" — which stays honest across both languages for these short nouns. */
export function deliverableLabel(id: string): string {
  const s = id.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
