/* Shared shapes returned by the campaigns API. */
export type Deliverable = { platform: string; type: string; quantity: number };

export type Campaign = {
  id: string;
  business_user_id: string;
  title: string;
  budget_amount: number | null;
  budget_currency: string | null;
  deliverables: Deliverable[];
  deadline: string | null;
  status: string;
};

export type Invitation = {
  id: string;
  campaign_id: string;
  influencer_user_id: string;
  status: string;
};

export type Proposal = {
  id: string;
  campaign_id: string;
  influencer_user_id: string;
  version: number;
  rate_amount: number;
  rate_currency: string;
  timeline_days: number;
  status: string;
};

export type CampaignDetail = Campaign & {
  invitations: Invitation[];
  proposals: Proposal[];
};

export type InvitationWithCampaign = Invitation & { campaign: Campaign };

export type Contract = {
  id: string;
  campaign_id: string;
  proposal_id: string;
  business_user_id: string;
  influencer_user_id: string;
  language: string;
  status: string;
  rate_amount: number;
  rate_currency: string;
  timeline_days: number;
  business_signed: boolean;
  influencer_signed: boolean;
  fully_signed: boolean;
};

export type ContractDetail = Contract & { body: string };

export type Escrow = {
  id: string;
  contract_id: string;
  campaign_id: string;
  business_user_id: string;
  influencer_user_id: string;
  amount: number;
  currency: string;
  commission_amount: number | null;
  status: string;
};

/* Answers to the two fixed profile questions; the question wording is product
   copy that lives in i18n, only the answers are stored. */
export type ProfileFaq = { audience?: string; brands?: string };

export type InfluencerProfile = {
  user_id: string;
  display_name: string | null;
  headline: string | null;
  location: string | null;
  avatar_media_id: string | null;
  avatar_url: string | null;
  bio: string | null;
  categories: string[];
  rate_card: Record<string, number>;
  follower_count: number | null;
  faq?: ProfileFaq | null;
  completion_percent: number;
  is_searchable: boolean;
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
  is_active: boolean;
};

export type PortfolioItem = { id: string; media_id: string; url: string };

export type SocialAccountPublic = {
  id: string;
  platform: string;
  handle: string;
  method: string;
  status: string;
  follower_count: number | null;
};

/* A revealed review as the public page shows it. reviewer_display_name is
   null when the reviewer has no public display name (business reviewers,
   until business profiles gain one). */
export type PublicReview = {
  stars: number;
  comment: string | null;
  created_at: string;
  reviewer_display_name: string | null;
};

/* Mirror of get_public_profile in backend/app/modules/profiles/service.py:
   the whole marketplace page in one aggregate. faq carries only the answered
   keys; packages are active only; reviews are revealed only, newest first. */
export type PublicProfile = {
  user_id: string;
  display_name: string | null;
  headline: string | null;
  location: string | null;
  avatar_url: string | null;
  bio: string | null;
  bio_fr: string | null;
  bio_en: string | null;
  categories: string[];
  follower_count: number | null;
  is_searchable: boolean;
  faq: ProfileFaq;
  average_stars: number | null;
  review_count: number;
  reviews: PublicReview[];
  packages: Package[];
  portfolio: PortfolioItem[];
  social_accounts: SocialAccountPublic[];
};

export type SearchResult = {
  user_id: string;
  display_name: string | null;
  headline: string | null;
  avatar_url: string | null;
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
