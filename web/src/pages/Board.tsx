import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CURRENCIES } from "../lib/campaignOptions";
import { PLATFORM_LABELS } from "../lib/platforms";
import type { OpenBrief } from "../lib/types";

/* The open board: briefs a creator can find without having been invited.

   WHY THE SCREEN EXISTS. Until now a campaign reached exactly the people the
   brand had already met — it was published, then specific creators were
   invited off a favourites list. A creator nobody had favourited had nothing
   to open, and a brand's reach was capped at the people it already knew. That
   is the cold start problem in both directions at once, and this page is the
   creator's half of closing it.

   CREATORS ONLY, and the route says so (App.tsx) because the API does: a
   business or agency calling GET /campaigns/open gets a 403 rather than an
   empty list. A brief carries a budget, a deadline and the shape of a brand's
   plans for the quarter — unlike a creator's storefront, which is public
   because it exists to be found.

   THE ORDER IS THE SERVER'S AND IS NEVER TOUCHED HERE. The API ranks by match
   score and then by newest, and re-sorting client-side would silently
   contradict the ranking the brand's targeting paid for — and would do it
   differently on every client. The rows render in the order they arrive.

   THE MATCH SCORE RANKS, IT DOES NOT FILTER. Every open brief is on every
   creator's board, including the ones scoring zero, and the page says so
   above the list rather than leaving creators to invent a theory about why
   some briefs are near the top. */

/* Mirrors MAX_MATCH_SCORE in backend/app/modules/campaigns/board.py
   (CATEGORY_WEIGHT 3 + COUNTRY_WEIGHT 2 + FOLLOWER_WEIGHT 1). Only ever used
   to say "n out of this" — no ranking decision is made client-side, so a
   drift here misstates a label and never reorders a board. */
const MAX_MATCH_SCORE = 6;

/* Mirrors MAX_NOTE_LENGTH in backend/app/modules/campaigns/schemas.py. */
const NOTE_MAX_LENGTH = 2000;

/* How well this brief fits, as one chip. Deliberately not a percentage: the
   score is three coarse weights and dressing it up as 67% would claim a
   precision the inputs do not have (the follower count is self-reported until
   platform analytics land). A brief that targets nothing scores zero for
   everybody, which is why zero reads as "open to all" rather than as a poor
   match — it usually means the brand named no preference at all. */
function MatchChip({ score }: { score: number }) {
  const { t } = useTranslation();
  const strong = score > 0;
  return (
    <span
      title={t("board.matchAria", { n: score, max: MAX_MATCH_SCORE })}
      style={{
        fontSize: 11.5, fontWeight: 600, padding: "3px 10px", borderRadius: 999, whiteSpace: "nowrap",
        color: strong ? "var(--teal-600)" : "var(--muted)",
        background: strong ? "#e7f6f0" : "var(--surface-2)"
      }}
    >
      {strong ? t("board.matchStrong") : t("board.matchNone")}
    </span>
  );
}

/* The creator's terms, which is what an application IS: the same rate,
   currency, timeline and optional note an invited creator sends, landing on
   the same version chain. The brand answers it from its campaign page exactly
   as it answers any other proposal. */
function ApplyForm({ brief, onApplied }: { brief: OpenBrief; onApplied: () => void }) {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [rate, setRate] = useState("");
  /* Defaulted to the brief's own currency where it has one: a chain is priced
     in one currency or it is two negotiations pretending to be one, and the
     brand already named which. */
  const [currency, setCurrency] = useState(brief.budget_currency ?? CURRENCIES[0]);
  const [days, setDays] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!rate || !days) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/campaigns/${brief.id}/apply`, {
        method: "POST",
        token,
        body: {
          rate_amount: Number(rate),
          rate_currency: currency,
          timeline_days: Number(days),
          note: note.trim() || null
        }
      });
      onApplied();
    } catch (err) {
      /* Mapped by STATUS CODE, never by reading the detail — the server
         sentence is written in English for the API and can be reworded at any
         time. A 409 here means exactly one thing: there is already a live
         proposal from this creator on this brief, and a second application
         would supersede terms the brand may be reading right now. */
      setError(
        err instanceof ApiError && err.status === 409
          ? t("board.applyConflict")
          : err instanceof Error ? err.message : "Error"
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}
      style={{ marginTop: 12, background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "var(--radius-sm)", padding: 14 }}>
      {error && <div className="alert alert-error">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 8 }}>
        <div>
          <label className="label" htmlFor={`apply-rate-${brief.id}`}>{t("board.applyRate")}</label>
          <input id={`apply-rate-${brief.id}`} className="input" inputMode="numeric" required value={rate}
            onChange={(e) => setRate(e.target.value.replace(/\D/g, ""))} placeholder="50000" />
        </div>
        <div>
          <label className="label" htmlFor={`apply-cur-${brief.id}`}>{t("board.applyCurrency")}</label>
          <select id={`apply-cur-${brief.id}`} className="select" value={currency}
            onChange={(e) => setCurrency(e.target.value)}>
            {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor={`apply-days-${brief.id}`}>{t("board.applyDays")}</label>
          <input id={`apply-days-${brief.id}`} className="input" inputMode="numeric" required value={days}
            onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))} placeholder="7" />
        </div>
      </div>
      <div style={{ marginTop: 10 }}>
        <label className="label" htmlFor={`apply-note-${brief.id}`}>{t("board.applyNote")}</label>
        <textarea id={`apply-note-${brief.id}`} className="input" rows={3} maxLength={NOTE_MAX_LENGTH}
          style={{ resize: "vertical" }} value={note} onChange={(e) => setNote(e.target.value)}
          placeholder={t("board.applyNotePlaceholder")} />
      </div>
      <button className="btn btn-primary" type="submit" disabled={busy || !rate || !days} style={{ marginTop: 10 }}>
        {busy ? t("auth.working") : t("board.applySend")}
      </button>
    </form>
  );
}

function BriefCard({ brief, onApplied }: { brief: OpenBrief; onApplied: (id: string) => void }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState(false);

  /* THE TWO REASONS THE BUTTON IS NOT OFFERED, both read straight off the
     payload rather than discovered from an error. Applying twice is a 409,
     and finding that out from the button rather than from a red box is the
     difference between a board and a trap. Being invited is not a refusal at
     all — the brief was addressed to this creator and the offer already
     exists on their invitations page, which is where answering it belongs. */
  const blocked = brief.has_applied || sent || brief.is_invited;

  return (
    <div className="card" style={{ marginTop: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div style={{ minWidth: 0 }}>
          {/* Who is asking, above the title: a creator decides whether to
              spend an evening pricing a brief partly on who wrote it. Null
              while the buyer has written no profile — the users table has
              only a phone number to offer, and that is never exposed. */}
          <div className="muted" style={{ fontSize: 12.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            {brief.business_company_name || t("board.unknownBrand")}
          </div>
          <strong style={{ fontFamily: "var(--font-display)", fontSize: 18 }}>{brief.title}</strong>
        </div>
        <MatchChip score={brief.match_score} />
      </div>

      <p className="muted" style={{ fontSize: 14, margin: "8px 0" }}>
        {brief.budget_amount
          ? `${brief.budget_amount.toLocaleString(i18n.language)} ${brief.budget_currency}`
          : t("campaign.noBudget")}
        {" · "}
        {brief.deadline ? `${t("board.deadline")} ${brief.deadline}` : t("board.noDeadline")}
      </p>

      {brief.description && (
        <p style={{ fontSize: 14, whiteSpace: "pre-wrap", margin: "0 0 10px" }}>{brief.description}</p>
      )}

      <div style={{ fontSize: 13.5 }}>
        <span className="muted" style={{ fontWeight: 600 }}>{t("board.deliverables")}: </span>
        {brief.deliverables.length === 0 ? (
          <span className="muted">{t("board.noDeliverables")}</span>
        ) : (
          brief.deliverables.map((d, i) => (
            <span key={i}>
              {i > 0 && ", "}
              {d.quantity} x {t(`deliverable.${d.type}`, d.type)} ({PLATFORM_LABELS[d.platform] ?? d.platform})
            </span>
          ))
        )}
      </div>

      {sent && <div className="alert alert-success" style={{ marginTop: 12, marginBottom: 0 }}>{t("board.applySent")}</div>}

      <div style={{ marginTop: 12, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        {!blocked && (
          <button type="button" className="btn btn-primary" onClick={() => setOpen((o) => !o)}>
            {open ? t("board.applyCancel") : t("board.apply")}
          </button>
        )}
        {/* The chip explains rather than just refuses. "Postuler" greyed out
            with nothing beside it is the version somebody clicks four times
            and then writes to support about. */}
        {brief.is_invited && (
          <>
            <span style={{ fontSize: 11.5, fontWeight: 600, padding: "3px 10px", borderRadius: 999, color: "var(--indigo)", background: "var(--surface-2)" }}>
              {t("board.invited")}
            </span>
            <span className="muted" style={{ fontSize: 13 }}>{t("board.invitedHint")}</span>
            <Link className="btn btn-ghost" to="/invitations">{t("board.invitedLink")}</Link>
          </>
        )}
        {!brief.is_invited && (brief.has_applied || sent) && (
          <>
            <span style={{ fontSize: 11.5, fontWeight: 600, padding: "3px 10px", borderRadius: 999, color: "var(--muted)", background: "var(--surface-2)" }}>
              {t("board.applied")}
            </span>
            <span className="muted" style={{ fontSize: 13 }}>{t("board.appliedHint")}</span>
          </>
        )}
      </div>

      {open && !blocked && (
        <ApplyForm
          brief={brief}
          onApplied={() => {
            /* Marked here rather than by reloading the whole board: the one
               fact that changed is this card's, and a refetch would reshuffle
               every other row under a creator who is still reading them. */
            setSent(true);
            setOpen(false);
            onApplied(brief.id);
          }}
        />
      )}
    </div>
  );
}

export default function BoardPage() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [briefs, setBriefs] = useState<OpenBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let live = true;
    api<OpenBrief[]>("/campaigns/open", { token })
      .then((rows) => {
        if (!live) return;
        // Stored exactly as they arrive. The ranking is the server's; see the
        // note at the top of this file.
        setBriefs(rows);
        setError(null);
      })
      .catch(() => { if (live) setError(t("board.loadFailed")); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [token, t]);

  function markApplied(id: string) {
    setBriefs((rows) => rows.map((r) => (r.id === id ? { ...r, has_applied: true } : r)));
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 820 }}>
        <h1 style={{ margin: 0 }}>{t("board.title")}</h1>
        <p className="muted" style={{ marginTop: 6 }}>{t("board.sub")}</p>
        {/* Said before the list and not after it: a creator who reaches the
            bottom of a board of poor matches has already decided the page is
            not for them. */}
        <p className="muted" style={{ fontSize: 13.5 }}>{t("board.rankHint")}</p>

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {loading ? (
          <p className="muted" style={{ marginTop: 18 }}>{t("discover.loading")}</p>
        ) : briefs.length === 0 ? (
          <div className="card" style={{ marginTop: 18 }}>
            <p style={{ margin: 0 }}>{t("board.empty")}</p>
            <p className="muted" style={{ fontSize: 13.5, margin: "8px 0 0" }}>{t("board.emptyHint")}</p>
          </div>
        ) : (
          briefs.map((brief) => <BriefCard key={brief.id} brief={brief} onApplied={markApplied} />)
        )}
      </div>
    </Layout>
  );
}
