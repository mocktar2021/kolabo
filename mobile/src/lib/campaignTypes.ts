/* The campaign shapes the brand side reads and writes, mirrored from
   backend/app/modules/campaigns/schemas.py (CampaignOut / CampaignCreate) and
   the web app's lib/types.ts + components/TargetingFields.tsx. Kept small: this
   slice creates, lists and publishes. Proposals and the negotiation thread are
   a later slice and their shapes land with it. */

/* A campaign deliverable uses `type`, not `deliverable_type` — that second
   spelling belongs to profile packages. The pair is validated against the
   platform catalog on the server, so DeliverableRows only ever builds a valid
   one. */
export type Deliverable = { platform: string; type: string; quantity: number };

export type Campaign = {
  id: string;
  business_user_id: string;
  title: string;
  description: string | null;
  budget_amount: number | null;
  budget_currency: string | null;
  deliverables: Deliverable[];
  deadline: string | null;
  status: string;
  is_direct: boolean;
  is_open: boolean;
  target_categories: string[];
  target_countries: string[];
  target_min_followers: number | null;
  target_max_followers: number | null;
};

/* One version of a negotiation chain, mirrored from ProposalOut. author_role
   says which side wrote it; expires_at is non-null only on a direct order,
   which is what lib/orders.ts uses to tell the two kinds of row apart. */
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
  author_role: string;
  expires_at: string | null;
  created_at: string;
};

/* A row of GET /campaigns/invitations/mine, mirrored from
   InvitationWithCampaign: the whole brief nested (the creator prices from
   it), the live version of the negotiation if one exists, and every version
   of that chain oldest-first. */
export type InvitationWithCampaign = {
  id: string;
  campaign_id: string;
  influencer_user_id: string;
  status: string;
  campaign: Campaign;
  business_company_name: string | null;
  proposal: Proposal | null;
  proposal_history: Proposal[];
};

/* Targeting as the form holds it. The follower bounds are strings, not
   numbers: an empty box means "no bound", and a number state cannot hold that
   without inventing a zero — which is a real value the server takes (ge=0),
   because the floor of "up to 5000" is zero followers, not one. */
export type Targeting = {
  is_open: boolean;
  categories: string[];
  countries: string[];
  minFollowers: string;
  maxFollowers: string;
};

export const EMPTY_TARGETING: Targeting = {
  is_open: false,
  categories: [],
  countries: [],
  minFollowers: "",
  maxFollowers: "",
};

/* The four targeting columns as they travel on a campaign body. */
export type TargetingBody = {
  is_open: boolean;
  target_categories: string[];
  target_countries: string[];
  target_min_followers: number | null;
  target_max_followers: number | null;
};

export function targetingBody(value: Targeting): TargetingBody {
  return {
    is_open: value.is_open,
    target_categories: value.categories,
    target_countries: value.countries,
    /* An empty box is null and not zero. Zero is a bound the brand did not
       set, and sending it would quietly rank every creator whose audience we
       do not know to the bottom of their own board. */
    target_min_followers: value.minFollowers === "" ? null : Number(value.minFollowers),
    target_max_followers: value.maxFollowers === "" ? null : Number(value.maxFollowers),
  };
}
