/* The open board — briefs a creator can find and apply to without an
   invitation. Mirrored from web/src/lib/types.ts (OpenBrief) and the
   campaigns/board API. */

export type BriefDeliverable = { platform: string; type: string; quantity: number };

export type OpenBrief = {
  id: string;
  title: string;
  description: string | null;
  business_company_name: string | null;
  /* How well the brief fits this creator's profile. The server ranks by it
     and never filters on it — a zero-score brief is on every board, "open to
     everyone". Rendered as a coarse chip, never a percentage. */
  match_score: number;
  budget_amount: number | null;
  budget_currency: string | null;
  deadline: string | null;
  deliverables: BriefDeliverable[];
  /* Read straight off the payload so the apply button is withheld before the
     click rather than after a 409 (has_applied) or a 403 (is_invited). */
  has_applied: boolean;
  is_invited: boolean;
};

/* Mirrors MAX_MATCH_SCORE in campaigns/board.py (only used for the "n / max"
   label; no ranking is done client-side). */
export const MAX_MATCH_SCORE = 6;
/* Mirrors MAX_NOTE_LENGTH in campaigns/schemas.py. */
export const NOTE_MAX_LENGTH = 2000;
