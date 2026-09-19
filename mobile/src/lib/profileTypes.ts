/* Shapes for the profiles module, mirrored from
   backend/app/modules/profiles/schemas.py. Only the fields the mobile screens
   read or send are typed here; the rest of the response is tolerated. */

export type InfluencerProfile = {
  user_id: string;
  display_name: string | null;
  headline: string | null;
  location: string | null;
  avatar_media_id: string | null;
  avatar_url: string | null;
  bio: string | null;
  bio_fr: string | null;
  bio_en: string | null;
  categories: string[];
  rate_card: Record<string, unknown>;
  faq: Record<string, string>;
  follower_count: number | null;
  birth_date: string | null;
  gender: string | null;
  languages: string[];
  completion_percent: number;
  is_searchable: boolean;
};

/* The PUT body. Every field is optional and the backend upsert is
   exclude_unset, so omitting a key leaves it alone; sending null clears it. */
export type InfluencerProfileInput = {
  display_name?: string | null;
  headline?: string | null;
  location?: string | null;
  avatar_media_id?: string | null;
  bio?: string | null;
  categories?: string[];
  rate_card?: Record<string, unknown>;
  faq?: Record<string, string>;
  follower_count?: number | null;
  birth_date?: string | null;
  gender?: string | null;
  languages?: string[];
};

export type Package = {
  id: string;
  user_id: string;
  platform: string;
  deliverable_type: string;
  title: string;
  description: string | null;
  price_amount: number;
  currency: string;
  quantity: number;
  duration_value: number | null;
  duration_unit: string | null;
  is_active: boolean;
};

export type PackageInput = {
  platform: string;
  deliverable_type: string;
  title: string;
  description: string | null;
  price_amount: number;
  currency: string;
  quantity: number;
  duration_value: number | null;
  duration_unit: string | null;
  is_active?: boolean;
};

/* One social account on a creator's profile, mirrored from
   schemas.SocialAccountOut.

   FOUR STATUSES, AND THREE OF THEM SAY DIFFERENT THINGS TO A BRAND.
   "pending" is a handle somebody typed and nothing has checked. "connected"
   is the creator having signed in to the platform, with Kolabo reading the
   account back through that platform's own API on the creator's own token:
   control of the handle is proved, identity is not. "verified" is an admin
   having read a real identity document, and it is never widened to cover a
   social login. "rejected" is an admin having looked and said no.
   lib/socialStatus.ts is the one place that turns the string into a chip.

   `status` IS NOT `follower_source`. The first answers "does this creator
   control this handle", the second answers "who supplied this number", and a
   verified handle carrying a number the creator typed is the normal state of
   almost every reviewed account on the platform today. */
export type SocialAccount = {
  id: string;
  platform: string;
  handle: string;
  method: string;
  status: string;
  follower_count: number | null;
  /* Where follower_count came from: "platform_api" when the platform itself
     stated it, "self_reported" when the creator typed it. Null when no
     number is recorded at all, and null on a row written before backend #161
     added the column, which is why lib/socialStatus draws no marker on a
     null rather than assuming the creator's word. */
  follower_source: string | null;
  /* When a platform API stated the number, and only ever set beside
     "platform_api", so a checked figure can be dated instead of quietly
     ageing. A naive UTC datetime string; lib/dates.formatDate reads it. */
  follower_verified_at: string | null;
  /* Present only on the connect response: whether enrichment filled anything. */
  enriched?: boolean;
};

export type OnboardingStatus = {
  has_bio: boolean;
  has_categories: boolean;
  has_pricing: boolean;
  has_packages: boolean;
  has_social: boolean;
  has_birth_date: boolean;
  active_package_count: number;
  is_live: boolean;
};

export type MediaOut = { id: string; url: string };
