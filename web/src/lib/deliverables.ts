/* Submitted work, as the client has to reason about it.

   The endpoints are in backend/app/modules/deliverables/router.py: submit
   (POST /deliverables), the history for one contract
   (GET /deliverables?contract_id=…), and the three answers —
   approve, request-changes, withdraw. Every one of them takes its actor from
   the bearer token and re-derives the parties from the contract, so there is
   nothing here to act on somebody else's contract with.

   NO TRAILING SLASH ON THE COLLECTION. Unlike /notifications/, these paths are
   declared as "" under their prefix, so "/deliverables" is the real URL and
   asking for it earns no 307. */
import type { UploadedMedia } from "./types";

/* How long the brand has to review before the escrow releases itself.

   MIRRORS settings.review_window_days in backend/app/core/config.py, and is
   duplicated here on purpose: it is shown to the creator as a promise about
   when they get paid, and no endpoint hands the number out. If the backend
   value changes, this one has to follow — which is why the string that uses it
   interpolates rather than hardcoding the digit twice. */
export const REVIEW_WINDOW_DAYS = 4;

/* A SUBMISSION IS AN IMMUTABLE ATTEMPT. "Request changes" does not reopen a
   row for editing — it closes that attempt and the creator's next hand-in is a
   new one. So a contract carries a LIST of these and the newest is the current
   state; the rest are the history both sides argue from, and the record an
   admin reads if it ever becomes a dispute. Mirror of SubmissionOut in
   backend/app/modules/deliverables/schemas.py. */
export type DeliverableStatus = "submitted" | "approved" | "changes_requested" | "withdrawn";

export type DeliverableSubmission = {
  id: string;
  contract_id: string;
  submitted_by_user_id: string;
  /* The published post. For influencer marketing this IS the deliverable, so
     it is the primary field; attachments are the supporting proof. Null when
     the creator sent files only — the server refuses a submission with
     neither. */
  link_url: string | null;
  note: string | null;
  status: DeliverableStatus;
  /* What the brand wants changed. Required by the server when asking for
     changes, so it is never null on a changes_requested row. */
  review_note: string | null;
  reviewed_by_user_id: string | null;
  /* Naive UTC like every other datetime from this API. */
  reviewed_at: string | null;
  created_at: string;
  attachments: string[];
};

/* The attempt the brand still owes an answer on, if there is one.

   AT MOST ONE, which the server enforces with a 409 rather than a unique
   column — "is there a live one" is a question about status. Found by status
   and not by taking the newest row, for the same reason the disputes screen
   does it: the newest row on a contract whose work was sent back is a CLOSED
   attempt, and showing it where the live one goes would offer the brand an
   Approve button for something it already rejected. */
export function openSubmission(rows: DeliverableSubmission[]): DeliverableSubmission | null {
  return rows.find((r) => r.status === "submitted") ?? null;
}

/* What the creator is sending. Kept here rather than inline in the panel so
   the shape and the endpoint stay described in one place. */
export type SubmissionDraft = {
  contract_id: string;
  link_url: string | null;
  note: string | null;
  media_ids: string[];
};

export function draftFrom(
  contractId: string,
  link: string,
  note: string,
  files: UploadedMedia[]
): SubmissionDraft {
  return {
    contract_id: contractId,
    link_url: link.trim() || null,
    note: note.trim() || null,
    media_ids: files.map((f) => f.id)
  };
}
