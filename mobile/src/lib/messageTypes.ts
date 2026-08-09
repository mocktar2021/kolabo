/* Messaging shapes, mirrored from backend/app/modules/messaging/schemas.py
   (ThreadOut / MessageOut) — the same payloads the web inbox reads. */

/* One conversation on the inbox: one row per PERSON, not per contract — a
   creator who worked with the same brand three times has one relationship,
   and the contracts are an attribute of it. */
export type MessageThread = {
  counterparty_user_id: string;
  counterparty_name: string | null;
  counterparty_avatar_url: string | null;
  contract_ids: string[];
  contract_count: number;
  contract_id: string;
  campaign_id: string;
  campaign_title: string | null;
  last_message: string | null;
  last_message_at: string | null;
  unread_count: number;
};

export type Message = {
  id: string;
  campaign_id: string;
  sender_user_id: string;
  recipient_user_id: string;
  body: string;
  created_at: string;
  read_at: string | null;
};

export const MESSAGE_MAX_LENGTH = 4000;
