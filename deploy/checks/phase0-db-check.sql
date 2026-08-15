-- Kolabo — Track A data-integrity check
--
-- READ-ONLY. There is no INSERT, UPDATE, DELETE or DDL anywhere in this file.
-- Safe to run against a live database, and safe to re-run.
--
-- Purpose: find rows that the missing terminal-state guards allowed to be
-- written before PRs #120-#126 closed them. The guards stop new bad rows; they
-- do not clean up old ones. This tells you whether there are any.
--
-- Column names were verified against the models at main @ b6a084b:
-- escrows.campaign_id, contract_events.event, proposals.author_role /
-- expires_at, campaign_invitations.status are all confirmed present.
--
-- HOW TO RUN (on the deploy host):
--
--   cd ~/kolabo/deploy
--   docker compose -f docker-compose.prod.yml exec -T db \
--     psql -U kolabo -d kolabo < checks/phase0-db-check.sql
--
-- psql continues past a failed statement by default, so if one check names a
-- column this build does not have, the rest still run. Keep the errors — they
-- are information too.

\pset border 2
\echo ''
\echo '=== KOLABO TRACK A — SUMMARY (0 everywhere means nothing to clean) ==='

SELECT check_id, finds, n FROM (
  SELECT 'C1' AS check_id, 'A1: proposals on invite-only briefs from never-invited creators' AS finds, (
    SELECT count(*) FROM proposals p JOIN campaigns c ON c.id = p.campaign_id
    WHERE c.is_direct = false AND c.is_open = false
      AND NOT EXISTS (SELECT 1 FROM campaign_invitations i
                      WHERE i.campaign_id = c.id AND i.influencer_user_id = p.influencer_user_id)
  ) AS n, 1 AS ord
  UNION ALL SELECT 'C2', 'A2: live (submitted) proposal versions sitting on cancelled campaigns', (
    SELECT count(*) FROM proposals p JOIN campaigns c ON c.id = p.campaign_id
    WHERE c.status = 'cancelled' AND p.status = 'submitted'
  ), 2
  UNION ALL SELECT 'C3', 'A2: proposal versions written AFTER the campaign was last touched (approx)', (
    SELECT count(*) FROM proposals p JOIN campaigns c ON c.id = p.campaign_id
    WHERE c.status = 'cancelled' AND p.created_at > c.updated_at
  ), 3
  UNION ALL SELECT 'C4', 'ORPHAN CHAINS: stranger proposals on someone else''s direct order', (
    SELECT count(*) FROM proposals p JOIN campaigns c ON c.id = p.campaign_id
    WHERE c.is_direct = true
      AND NOT EXISTS (SELECT 1 FROM campaign_invitations i
                      WHERE i.campaign_id = c.id AND i.influencer_user_id = p.influencer_user_id)
  ), 4
  UNION ALL SELECT 'C5', 'W1: contracts now SIGNED that carry a cancelled event (resurrected)', (
    SELECT count(*) FROM contracts ct
    WHERE ct.status = 'signed'
      AND EXISTS (SELECT 1 FROM contract_events e WHERE e.contract_id = ct.id AND e.event = 'cancelled')
  ), 5
  UNION ALL SELECT 'C6', 'W1: signature events recorded AFTER a cancellation event', (
    SELECT count(*) FROM contract_events s
    JOIN contract_events x ON x.contract_id = s.contract_id AND x.event = 'cancelled'
    WHERE s.event IN ('signed_business','signed_influencer','fully_signed') AND s.created_at > x.created_at
  ), 6
  UNION ALL SELECT 'C7', 'W1 MONEY: escrows on contracts that were ever cancelled', (
    SELECT count(*) FROM escrows e
    WHERE EXISTS (SELECT 1 FROM contract_events ev WHERE ev.contract_id = e.contract_id AND ev.event = 'cancelled')
  ), 7
  UNION ALL SELECT 'C8', 'contracts hanging off a cancelled campaign', (
    SELECT count(*) FROM contracts ct JOIN campaigns c ON c.id = ct.campaign_id WHERE c.status = 'cancelled'
  ), 8
  UNION ALL SELECT 'C9', 'W2 TRIAGE: contracts accepted on a business-authored version (incl. legit order accepts)', (
    SELECT count(*) FROM contracts ct JOIN proposals p ON p.id = ct.proposal_id WHERE p.author_role = 'business'
  ), 9
  UNION ALL SELECT 'C10', 'A4: invitations issued after that campaign''s escrow was already resolved', (
    SELECT count(*) FROM campaign_invitations i JOIN escrows e ON e.campaign_id = i.campaign_id
    WHERE e.status IN ('released','refunded') AND e.resolved_at IS NOT NULL AND i.created_at > e.resolved_at
  ), 10
  UNION ALL SELECT 'C11', 'duplicate invitations (blocks the unique constraint until cleaned)', (
    SELECT coalesce(sum(k - 1), 0) FROM (
      SELECT count(*) AS k FROM campaign_invitations
      GROUP BY campaign_id, influencer_user_id HAVING count(*) > 1
    ) d
  ), 11
  UNION ALL SELECT 'C12', 'cancel-no-cascade residue: invitations still ''invited'' on cancelled campaigns', (
    SELECT count(*) FROM campaign_invitations i JOIN campaigns c ON c.id = i.campaign_id
    WHERE c.status = 'cancelled' AND i.status = 'invited'
  ), 12
  UNION ALL SELECT 'C13', 'A3: proposals opened after that campaign''s escrow had already resolved', (
    SELECT count(*) FROM proposals p JOIN escrows e ON e.campaign_id = p.campaign_id
    WHERE e.status IN ('released','refunded') AND e.resolved_at IS NOT NULL AND p.created_at > e.resolved_at
  ), 13
  UNION ALL SELECT 'C14', 'oversized uploads (>5 MB) — the cap that only landed in #122', (
    SELECT count(*) FROM media_assets WHERE octet_length(data) > 5242880
  ), 14
  UNION ALL SELECT 'C15', 'largest single upload, in MB (context for C14)', (
    SELECT coalesce(round(max(octet_length(data)) / 1048576.0), 0)::bigint FROM media_assets
  ), 15
) s ORDER BY ord;

\echo ''
\echo '=== SCALE CONTEXT (how much data is behind those numbers) ==='

SELECT 'campaigns' AS tbl, count(*) AS n, count(*) FILTER (WHERE status = 'cancelled') AS flagged FROM campaigns
UNION ALL SELECT 'proposals', count(*), count(*) FILTER (WHERE status = 'submitted') FROM proposals
UNION ALL SELECT 'campaign_invitations', count(*), count(*) FILTER (WHERE status = 'invited') FROM campaign_invitations
UNION ALL SELECT 'contracts', count(*), count(*) FILTER (WHERE status = 'signed') FROM contracts
UNION ALL SELECT 'escrows', count(*), count(*) FILTER (WHERE status = 'held') FROM escrows
UNION ALL SELECT 'media_assets', count(*), 0 FROM media_assets;

\echo ''
\echo '=== DETAIL — only meaningful for checks whose count above was > 0 ==='
\echo '--- C4 detail: orphan chains on direct orders (the sweep hazard) ---'

SELECT p.id AS proposal_id, p.campaign_id, p.influencer_user_id, p.version,
       p.status, p.expires_at, c.status AS campaign_status
FROM proposals p JOIN campaigns c ON c.id = p.campaign_id
WHERE c.is_direct = true
  AND NOT EXISTS (SELECT 1 FROM campaign_invitations i
                  WHERE i.campaign_id = c.id AND i.influencer_user_id = p.influencer_user_id)
ORDER BY p.created_at DESC LIMIT 25;

\echo '--- C2/C3 detail: live proposals on cancelled campaigns ---'

SELECT p.id AS proposal_id, p.campaign_id, p.version, p.author_role, p.status,
       p.created_at, c.updated_at AS campaign_last_touched
FROM proposals p JOIN campaigns c ON c.id = p.campaign_id
WHERE c.status = 'cancelled' AND p.status = 'submitted'
ORDER BY p.created_at DESC LIMIT 25;

\echo '--- C5/C6/C7 detail: contracts with a cancellation in their history ---'

SELECT ct.id AS contract_id, ct.status AS contract_status, ct.rate_amount, ct.rate_currency,
       (SELECT string_agg(e.event || '@' || to_char(e.created_at,'MM-DD HH24:MI'), ' -> ' ORDER BY e.created_at)
        FROM contract_events e WHERE e.contract_id = ct.id) AS history,
       (SELECT es.status FROM escrows es WHERE es.contract_id = ct.id) AS escrow_status
FROM contracts ct
WHERE EXISTS (SELECT 1 FROM contract_events e WHERE e.contract_id = ct.id AND e.event = 'cancelled')
ORDER BY ct.created_at DESC LIMIT 25;

\echo '--- C8 detail: contracts on cancelled campaigns ---'

SELECT ct.id AS contract_id, ct.status, c.id AS campaign_id, c.title,
       (SELECT es.status FROM escrows es WHERE es.contract_id = ct.id) AS escrow_status
FROM contracts ct JOIN campaigns c ON c.id = ct.campaign_id
WHERE c.status = 'cancelled' ORDER BY ct.created_at DESC LIMIT 25;

\echo '--- C11 detail: duplicate invitations ---'

SELECT campaign_id, influencer_user_id, count(*) AS times_invited
FROM campaign_invitations GROUP BY campaign_id, influencer_user_id HAVING count(*) > 1
ORDER BY times_invited DESC LIMIT 25;

\echo ''
\echo '=== END. Nothing was modified. ==='
