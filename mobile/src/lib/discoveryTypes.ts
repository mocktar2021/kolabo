/* Discovery and direct-order shapes, mirrored from the backend schemas:
   InfluencerSearchResult and SocialSummary from modules/discovery/schemas.py,
   PublicProfileOut from modules/profiles/schemas.py (the fields this client
   renders), and OrderOut from modules/campaigns/schemas.py. */

import type { Package, SocialAccount } from "./profileTypes";

export type SocialSummary = {
  platform: string;
  handle: string;
  follower_count: number | null;
};

export type SearchResult = {
  user_id: string;
  display_name: string | null;
  headline: string | null;
  location: string | null;
  avatar_url: string | null;
  cover_url: string | null;
  socials: SocialSummary[];
  bio: string | null;
  categories: string[];
  follower_count: number | null;
  country_code: string;
  is_verified: boolean;
  starting_price_amount: number | null;
  starting_price_currency: string | null;
  average_stars: number | null;
  review_count: number;
};

/* The public storefront. portfolio and faq exist on the API payload but are
   not typed here: this client does not render them yet, and response_model
   guarantees nothing typed here is missing. */
export type PublicProfileData = {
  user_id: string;
  display_name: string | null;
  headline: string | null;
  location: string | null;
  avatar_url: string | null;
  bio: string | null;
  categories: string[];
  languages: string[];
  follower_count: number | null;
  is_searchable: boolean;
  average_stars: number | null;
  review_count: number;
  packages: Package[];
  /* THE WHOLE ACCOUNT, NOT THREE FIELDS OF IT. The payload has been
     list[SocialAccountOut] since this endpoint existed; typing a three field
     subset of it here is what kept the account status and both provenance
     columns off the one page a brand reads before it spends. */
  social_accounts: SocialAccount[];
};

/* What the buyer gets back from POST /campaigns/orders: where the order
   lives, which proposal the creator answers, and the deadline they answer
   by. */
export type DirectOrder = {
  campaign_id: string;
  proposal_id: string;
  expires_at: string | null;
};
