/* Mirror of the backend platform map (backend/app/core/platforms.py). A
   deliverable is only offered where it actually exists, so the form cannot
   build a package the API will reject with a 400. */
export type PlatformId =
  | "instagram" | "tiktok" | "facebook" | "youtube" | "snapchat"
  | "x" | "threads" | "linkedin" | "whatsapp" | "discord" | "ugc";

export const PLATFORM_DELIVERABLES: Record<PlatformId, string[]> = {
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
  ugc: ["ugc_video", "ugc_photo"]
};

/* Everything a creator can price and sell. Wider than the list of accounts
   they can connect: UGC is made for the brand to run as its own ad and is
   never posted on the creator's account, so it is sellable but not
   connectable. */
export const SELLABLE_PLATFORMS: { id: PlatformId; label: string }[] = [
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
  { id: "ugc", label: "UGC" }
];

export const PLATFORM_LABELS: Record<string, string> = Object.fromEntries(
  SELLABLE_PLATFORMS.map((p) => [p.id, p.label])
);

export function deliverablesFor(platform: string): string[] {
  return PLATFORM_DELIVERABLES[platform as PlatformId] ?? [];
}
