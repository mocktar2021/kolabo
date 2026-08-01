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

/* Which side wrote a proposal version. The creator opens a chain and the
   business answers inside it, so a version carries an author even though the
   whole chain is filed under the creator it belongs to. */
export type ProposalAuthorRole = "influencer" | "business";

/* One version of one negotiation — a complete offer, never a diff: a business
   reply that counters nothing repeats the previous rate and timeline, so no
   row has to be read against the one above it to know what is on the table.

   note is what the numbers mean ("the budget stops at 40k", "can you do it in
   five days"), capped at 2000 characters server-side. display_name and
   avatar_url identify the creator behind the chain and are null until they
   have a profile — the users table holds only a phone number besides, and a
   phone number is never handed to the other side of a deal. */
export type Proposal = {
  id: string;
  campaign_id: string;
  influencer_user_id: string;
  version: number;
  rate_amount: number;
  rate_currency: string;
  timeline_days: number;
  status: string;
  note: string | null;
  author_role: ProposalAuthorRole;
  display_name: string | null;
  avatar_url: string | null;
};

/* What POST /campaigns/orders answers with. Deliberately not the whole
   campaign: what the buyer needs back is where the order lives, which offer
   the creator is answering, and the deadline they are answering by.

   No contract id, because there is no contract yet — one is written only if
   the creator accepts, which is also why no money has moved at this point. */
export type DirectOrder = {
  campaign_id: string;
  proposal_id: string;
  expires_at: string | null;
};

/* proposals is a flat list, not a list of chains: every version of every
   negotiation on the campaign, oldest first, capped at the twenty most recent
   (the cap is taken from the recent end, because the last version is the live
   offer and the only one that can be accepted). Chains are the rows sharing an
   influencer_user_id, ordered by version — CampaignDetail.tsx groups them. */
export type CampaignDetail = Campaign & {
  invitations: Invitation[];
  proposals: Proposal[];
};

/* A row of GET /discovery/favorites. Everything past the id is optional and
   stays optional: a creator can be favourited before they have filled in
   anything, and an incomplete card is still usable while a failed request is
   not. country_code is the one field taken from the users table — the only
   other identifier a user row holds is a phone number, which never reaches a
   payload. */
export type Favorite = {
  influencer_user_id: string;
  display_name: string | null;
  avatar_url: string | null;
  headline: string | null;
  country_code: string | null;
};

/* A row of GET /campaigns/invitations/mine. The brand's company name rides at
   row level rather than inside campaign: it is who is asking, not part of the
   brief. It can be null while a business has not filled its profile, so the
   UI falls back to a generic "Marque" label. Everything the creator prices
   against — title, budget, deadline, deliverables — comes nested under
   campaign. */
export type InvitationWithCampaign = Invitation & {
  campaign: Campaign;
  business_company_name: string | null;
};

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

/* Referrals (GET /auth/me/referral).

   status is the only part of this that carries money: "signed_up" means the
   invited account exists, "ordered" means its first order completed — which
   is the event that actually mints credit for both sides. Keeping the two
   apart is what lets the dashboard show a referrer why a name in the list has
   not paid them anything yet. */
export type ReferralStatus = "signed_up" | "ordered";

/* role is the referred account's role. It is a plain string rather than the
   Role union because the label only needs the creator/brand split, and
   isBusinessLike already folds agencies in with businesses. */
export type ReferralEntry = {
  joined_at: string;
  role: string;
  status: ReferralStatus;
};

export type ReferralInfo = {
  code: string;
  referred_count: number;
  referred_creators: number;
  referred_businesses: number;
  credit_total: number;
  credit_currency: string;
  referrals: ReferralEntry[];
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
  /* Identity fields. birth_date (YYYY-MM-DD, 18+ enforced server-side) and
     gender stay private; languages (codes like "fr") shows publicly. */
  birth_date: string | null;
  gender: "female" | "male" | "other" | "prefer_not_to_say" | null;
  languages: string[];
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
  /* How many units the buyer gets (e.g. 3 stories). Defaults to 1. */
  quantity: number;
  /* Optional content length. Value and unit travel together or are both
     null; the server enforces the pairing. */
  duration_value: number | null;
  duration_unit: "seconds" | "minutes" | "hours" | null;
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
