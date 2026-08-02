/* Shared shapes returned by the campaigns API. */
export type Deliverable = { platform: string; type: string; quantity: number };

export type Campaign = {
  id: string;
  business_user_id: string;
  title: string;
  /* The brief in prose: context, tone, what the brand is trying to say.
     Capped at 5000 characters server-side, and null on every campaign written
     before the column existed as well as on direct orders — an order carries
     terms, not a brief — so every reader has to handle its absence.

     It is description and not terms, which is why it stays editable for the
     whole life of a campaign while the budget does not: rewriting it does not
     change what a creator priced against. */
  description: string | null;
  budget_amount: number | null;
  budget_currency: string | null;
  deliverables: Deliverable[];
  deadline: string | null;
  status: string;
  /* True when the campaign is really a direct order: one creator, the buyer's
     offer already on the table, nobody else bidding. The client needs it to
     label the card as an order rather than a brief — and to know not to offer
     the edit form, because PATCH answers 400 on one. An order's terms are a
     negotiation, and the way to change them is to counter. */
  is_direct: boolean;
  /* Whether the brief is on the open board, where any creator may apply to it
     without an invitation. On the ordinary campaign payload and not only on
     the board's own, because the buyer's list of its campaigns has to be able
     to say which of them strangers can answer — that is the difference
     between a brief with three invited creators and a brief that may collect
     thirty applications overnight. */
  is_open: boolean;
  /* Who the brand hopes to reach. THESE FOUR RANK, THEY DO NOT EXCLUDE: a
     creator who matches sees the brief first, and every creator sees it.
     backend/app/modules/campaigns/board.py holds the reasoning; the naming
     says "target" rather than "require" for exactly that reason.

     The two lists are NOT NULL server-side and arrive as [] when nothing is
     targeted, so no reader has to handle a null. The two bounds are genuinely
     nullable — an unnamed end of the band is open rather than zero or
     infinite. */
  target_categories: string[];
  target_countries: string[];
  target_min_followers: number | null;
  target_max_followers: number | null;
};

/* One row of the open board (GET /campaigns/open). Mirror of OpenBriefOut in
   backend/app/modules/campaigns/schemas.py.

   The whole brief and not a summary of it, because a creator decides from
   this card whether to spend an evening pricing the job — and deliverables,
   budget and deadline are exactly what they would be pricing. Campaign
   already carries all of it, so this only adds what the board itself knows.

   match_score is a small bounded whole number (0..MAX_MATCH_SCORE in
   campaigns/board.py) and is A RANKING HINT, NOT A VERDICT: a zero-scoring
   brief is just as applicable as a perfect one, which is the entire point of
   a soft filter. It is shown rather than hidden, because a board that
   silently reorders itself is a board creators invent theories about.

   has_applied and is_invited keep the card honest about what this creator has
   already done here — applying twice is refused with a 409, and finding that
   out from the button rather than from the error is the difference between a
   board and a trap. */
export type OpenBrief = Campaign & {
  /* Who is asking. Null while the buyer has written no profile — the users
     table has only a phone number to offer, and that is never exposed. */
  business_company_name: string | null;
  match_score: number;
  has_applied: boolean;
  is_invited: boolean;
};

/* How a creator appears on any row a business reads: favourites, campaign
   invitations, proposals. Mirror of CreatorIdentity in
   backend/app/modules/campaigns/schemas.py, filled by app.core.identity.

   One shape rather than three, because a business comparing an invitation
   against a proposal is looking at the same person and used to be shown a raw
   user id on one and a name on the other. CreatorChip renders it.

   Every field is null until the creator has something to put in it — somebody
   can be invited the day they sign up. Nothing here is ever filled in from the
   users table: the only identifier it holds is a phone number, and a phone
   number is never handed to the other side of a deal. top_follower_count is
   the audience of the single biggest platform and never a total across them,
   so the same follower is not counted twice. */
export type CreatorIdentity = {
  display_name: string | null;
  avatar_url: string | null;
  top_platform: string | null;
  top_follower_count: number | null;
};

/* An invitation as the invited creator reads it. No identity on this one, and
   deliberately: every row in the creator's own list is them, so naming them
   would cost a query to tell somebody their own name. */
export type Invitation = {
  id: string;
  campaign_id: string;
  influencer_user_id: string;
  status: string;
};

/* The same row on the business's campaign page, where naming the creator is
   the entire point — this list used to render a bare user id beside a
   proposals list that rendered names. */
export type CampaignInvitation = Invitation & CreatorIdentity;

/* Which side wrote a proposal version. The creator opens a chain and the
   business answers inside it, so a version carries an author even though the
   whole chain is filed under the creator it belongs to. A direct order is the
   case where "business" comes first: the buyer made the offer. */
export type ProposalAuthorRole = "influencer" | "business";

/* One version of one negotiation — a complete offer, never a diff: a business
   reply that counters nothing repeats the previous rate and timeline, so no
   row has to be read against the one above it to know what is on the table.

   note is what the numbers mean ("the budget stops at 40k", "can you do it in
   five days"), capped at 2000 characters server-side. The CreatorIdentity
   fields name the creator behind the chain and are null until they have a
   profile — the users table holds only a phone number besides, and a phone
   number is never handed to the other side of a deal.

   expires_at is set only on a direct order, and it is the field that tells
   the two kinds of row apart: a brief's proposals stay open indefinitely
   because leaving one open promised nothing, while an order has a buyer
   waiting on a price they already named. The datetime arrives naive UTC (no
   suffix), so anything reading it has to say so before parsing. */
export type Proposal = CreatorIdentity & {
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
  expires_at: string | null;
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

/* The receipt for a hard delete (DELETE /campaigns/{id}). The id is echoed
   back because the row it names no longer exists to be fetched, and a client
   that removed the wrong card from its list has no way to find out otherwise. */
export type CampaignDeleted = {
  id: string;
  deleted: boolean;
};

/* proposals is a flat list, not a list of chains: every version of every
   negotiation on the campaign, oldest first, capped at the twenty most recent
   (the cap is taken from the recent end, because the last version is the live
   offer and the only one that can be accepted). Chains are the rows sharing an
   influencer_user_id, ordered by version — CampaignDetail.tsx groups them. */
export type CampaignDetail = Campaign & {
  invitations: CampaignInvitation[];
  proposals: Proposal[];
};

/* A row of GET /discovery/favorites. Everything past the id is optional and
   stays optional: a creator can be favourited before they have filled in
   anything, and an incomplete card is still usable while a failed request is
   not. country_code is the one field taken from the users table — the only
   other identifier a user row holds is a phone number, which never reaches a
   payload.

   headline is gone: the API stopped sending it. It was only ever a subtitle
   under the name, and creators write their name into it, so the card said the
   same thing twice. The audience number is what a business shortlists on, and
   it arrives with the rest of the shared identity. */
export type Favorite = CreatorIdentity & {
  influencer_user_id: string;
  country_code: string | null;
};

/* A row of GET /campaigns/invitations/mine. The brand's company name rides at
   row level rather than inside campaign: it is who is asking, not part of the
   brief. It can be null while a business has not filled its profile, so the
   UI falls back to a generic "Marque" label. Everything the creator prices
   against — title, budget, deadline, deliverables — comes nested under
   campaign.

   proposal is the live version of the negotiation, null when nothing has been
   offered yet. On a brief it is context; on a direct order it IS the order —
   the buyer's offer, and the id the creator accepts or declines with. */
export type InvitationWithCampaign = Invitation & {
  campaign: Campaign;
  business_company_name: string | null;
  proposal: Proposal | null;
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

/* One conversation on the inbox screen (GET /messaging/threads).

   A row per PERSON, named by the OTHER one: a creator's inbox says "Maison
   Kola", a brand's says "Ama K.". It used to be a row per CONTRACT, which
   gave a creator on their third job with the same brand three inboxes with
   the same name on them — the relationship is worth more each time it
   repeats, and the shape was chopping it up in response. The contracts are
   now an attribute of the row.

   contract_ids holds every contract between the two, NEWEST FIRST, and
   contract_count is how many: "we have done four jobs together" is a fact
   about a relationship worth showing, and a client that wants to link to one
   specific job still can.

   contract_id, campaign_id and campaign_title describe the NEWEST shared
   contract only. They are kept spelled out because the header wants to name
   the job the two of them are currently on, and because a client written
   against the per-contract shape keeps rendering — which is also why
   ContractsMenu falls back to contract_id when contract_ids is empty.

   counterparty_name is null when the other side has written no profile — the
   same rule identity follows everywhere else, and for the same reason: the
   users table holds only a phone number, and a phone number is never handed
   to the other side of a deal. counterparty_avatar_url is only ever set for a
   creator; a business has a company name and no avatar in this system.

   unread_count is across the WHOLE relationship rather than one job: an
   unanswered question is unanswered whichever contract it was asked under.

   last_message_at arrives naive UTC like every other datetime here, so it
   goes through parseApiDate before it is turned into "il y a 2 h". */
export type MessageThread = {
  counterparty_user_id: string;
  counterparty_name: string | null;
  counterparty_avatar_url: string | null;
  /* Every contract between the two, newest first, and how many there are. */
  contract_ids: string[];
  contract_count: number;
  /* The newest shared contract and its campaign — the job they are on now. */
  contract_id: string;
  campaign_id: string;
  campaign_title: string | null;
  last_message: string | null;
  last_message_at: string | null;
  unread_count: number;
};

/* One message in a thread. read_at is a timestamp rather than a flag because
   in a dispute the useful fact is when a specific message was seen, not how
   many are outstanding — and it is null until the recipient opens the thread,
   which is the only thing that stamps it.

   campaign_id stays on every row, including messages sent to a PERSON through
   the counterparty endpoint (the server stamps those with the most recent
   shared contract's campaign). It is provenance — which job a message was
   about, which is what a dispute reads — and never an authorisation: the
   contract is what decides who may see what. */
export type Message = {
  id: string;
  campaign_id: string;
  sender_user_id: string;
  recipient_user_id: string;
  body: string;
  created_at: string;
  read_at: string | null;
};

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

/* One line of a creator's statement (GET /payments/earnings). Mirror of
   EarningPaymentOut in backend/app/modules/payments/schemas.py.

   gross, commission and net all three, side by side. Net is the number that
   matters — it is what reaches the wallet — but showing it alone would make
   the platform's cut invisible, and a fee somebody cannot see is a fee they
   assume was a mistake. The three columns are how a creator checks our
   arithmetic against their own.

   counterparty_name is the buyer's company name, null while they have written
   no profile: the users row holds nothing else but a phone number, and a
   phone number is never handed to the other side of a deal.

   date is when the payment settled if it settled and when it was funded if it
   has not — one column, because a statement line has one date on it. Naive
   UTC like every other datetime from this API, so it goes through
   parseApiDate. Null only on rows predating the columns it is read from. */
export type EarningPayment = {
  escrow_id: string;
  contract_id: string;
  campaign_title: string | null;
  counterparty_name: string | null;
  gross: number;
  commission: number;
  net: number;
  currency: string;
  status: string;
  date: string | null;
};

/* The creator's money in three states (GET /payments/earnings).

   EACH TOTAL IS A MAP OF CURRENCY TO AMOUNT AND NEVER A SINGLE NUMBER, which
   is the type doing the work the product rule needs: there is no field here a
   client could render as "total earnings" across two markets, because XOF and
   GHS are not addends and a figure spanning both would be meaningless on the
   screen a creator trusts most.

   disputed is its own field and NOT part of pending. Pending is money already
   paid into escrow that releases on delivery — a promise with a date on it.
   Disputed money has no date and may go back to the buyer when an admin
   decides. Merging them would mean "expect this" where the truth is "argue
   for this".

   Every figure is net of commission: the platform's cut comes off at release,
   so a gross total is one that never reaches a wallet.

   A business calling this endpoint gets empty maps and an empty list, on
   purpose — buyer-side SPEND is a different question with the opposite sign
   and has its own endpoint, GET /payments/spend, typed just below. */
export type Earnings = {
  earned: Record<string, number>;
  pending: Record<string, number>;
  disputed: Record<string, number>;
  payments: EarningPayment[];
};

/* One line of a BUYER's statement (GET /payments/spend). Mirror of
   SpendPaymentOut in backend/app/modules/payments/schemas.py.

   NO COMMISSION COLUMNS, which is the visible difference from EarningPayment
   and the whole reason the two are separate types rather than one with
   optional fields. The platform's cut comes out of the creator's release and
   not out of the buyer's payment: a brand that funded 100000 paid 100000, and
   a "net" field here would invite it to think it had been charged something
   it was not.

   refunded_amount is the part of this contract that came back after a dispute
   split, and it is zero on almost every row. It is ON THE LINE and not only
   in the totals because otherwise a split shows 60000 spent against a
   contract the buyer funded with 100000, and the missing 40000 sits in a
   total with no line to trace it to.

   counterparty_name is the CREATOR here, where on an earnings row it is the
   buyer — the field is "the other party", resolved by whichever side is
   reading. Null before they have written a profile, never a phone number
   standing in for it.

   date is when it settled if it settled and when it was funded if it has not,
   naive UTC like every other datetime from this API, so it goes through
   parseApiDate. */
export type SpendPayment = {
  escrow_id: string;
  contract_id: string;
  campaign_title: string | null;
  counterparty_name: string | null;
  amount: number;
  refunded_amount: number;
  currency: string;
  status: string;
  date: string | null;
};

/* The buyer's money in FOUR states (GET /payments/spend).

   Four rather than the earnings screen's three because refunded money is a
   real line in a buyer's ledger and no line at all in a creator's: they paid
   it and got it back, and both halves have to be visible or the arithmetic
   does not close. For the creator it is money that never arrived.

   Every total is a map of currency to amount for exactly the reason Earnings
   is, and the rule is the same one: XOF and GHS are not addends, so there is
   no field here a client could render as "total spend" across two markets.

   disputed stays out of pending for the mirror of the reason it does on the
   creator's screen: pending is money the buyer expects to lose, disputed is
   money they may get back.

   A creator calling this endpoint gets four empty maps and an empty list, on
   purpose — they are on no escrow as the buyer. */
export type Spend = {
  spent: Record<string, number>;
  pending: Record<string, number>;
  disputed: Record<string, number>;
  refunded: Record<string, number>;
  payments: SpendPayment[];
};

/* What POST /profiles/{userId}/media answers with (MediaOut). The id is what
   gets attached to things — a portfolio row, an avatar, a piece of dispute
   evidence — and the url is the path to serve it back from, which still needs
   mediaSrc() to become absolute. */
export type UploadedMedia = { id: string; url: string };

/* Disputes (KOL-37).

   Mirror of DISPUTE_REASONS in backend/app/modules/payments/models.py. A
   closed set rather than free text because two things read it and neither
   reads prose: the admin queue triages by it, and it is what fraud analytics
   will eventually count. The statement is where the words go. */
export type DisputeReason =
  | "not_delivered"
  | "late"
  | "wrong_content"
  | "quality"
  | "payment_issue"
  | "other";

/* awaiting_response is the 72 h window that belongs to the two parties;
   awaiting_admin is the queue. resolved and withdrawn are closed records —
   they are read, never written to, and they do not stop a new dispute being
   raised on the same escrow. */
export type DisputeStatus =
  | "awaiting_response"
  | "awaiting_admin"
  | "resolved"
  | "withdrawn";

/* One case, as both parties and an admin read it.

   attachments are the opening statement's evidence only — server paths like
   "/profiles/media/{id}", so they go through mediaSrc() before they reach an
   <img>. Evidence on later messages hangs off the messages themselves.

   released_amount / refunded_amount / resolution are null until an admin has
   decided, and they are the decision itself rather than a copy of the escrow:
   the escrow says where the money ended up, these say what was ruled.

   respond_by and created_at arrive naive UTC like every other datetime from
   this API, so both go through parseApiDate.

   escrow is nested by every dispute endpoint, but the response schema types
   it optional, so it stays nullable here rather than being asserted away. */
export type Dispute = {
  id: string;
  escrow_id: string;
  opened_by_user_id: string;
  reason: DisputeReason;
  statement: string;
  status: DisputeStatus;
  respond_by: string;
  resolved_at: string | null;
  resolution: string | null;
  released_amount: number | null;
  refunded_amount: number | null;
  resolved_by: string | null;
  created_at: string;
  attachments: string[];
  escrow: Escrow | null;
};

/* One turn in the thread the two parties settle it in.

   No recipient: a dispute has exactly two parties and an audience of admins,
   so who a message is FOR is never in question — only who wrote it, which is
   what turns the thread into "Vous" and the other side's name. */
export type DisputeThreadMessage = {
  id: string;
  author_user_id: string;
  body: string;
  created_at: string;
  attachments: string[];
};

/* GET /payments/disputes/{id}: the same case with its thread attached. The
   list endpoint deliberately does not carry messages — a list of ten cases
   would pull every word ever written in any of them. */
export type DisputeCase = Dispute & { messages: DisputeThreadMessage[] };

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
