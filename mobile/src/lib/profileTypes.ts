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

export type SocialAccount = {
  id: string;
  platform: string;
  handle: string;
  method: string;
  status: string;
  follower_count: number | null;
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
