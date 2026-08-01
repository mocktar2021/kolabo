import { useTranslation } from "react-i18next";
import { SELLABLE_PLATFORMS, deliverablesFor } from "../lib/platforms";
import type { Deliverable } from "../lib/types";

/* Quantity choices for a deliverable row. A dropdown rather than a free text
   field: a fat finger on a number input turns "10 reels" into "100 reels" and
   the brand only finds out when the proposals come back absurd. Twenty is far
   past any real brief, and this is the same control the package form uses. */
const QUANTITIES = Array.from({ length: 20 }, (_, i) => i + 1);

/* A fresh row starts on the first platform's first deliverable so the pair is
   valid by construction; the backend validates every pair against the same
   catalog and answers 400 for anything else. */
export function emptyDeliverable(): Deliverable {
  const platform = SELLABLE_PLATFORMS[0].id;
  return { platform, type: deliverablesFor(platform)[0], quantity: 1 };
}

/* The deliverable rows of a brief, lifted out of CampaignNew so the edit form
   on CampaignDetail is the same control rather than a second copy of it. Two
   copies would be two places where switching platform forgets to reset the
   deliverable type, and that bug only ever surfaces as a 400 on submit.

   Controlled: the parent owns the list. The create form posts it whole, and
   the edit form has to diff it against what the campaign already holds to
   know whether it changed at all.

   disabled is the locked case, not a loading case. A published campaign that
   somebody has already priced against keeps its deliverables read-only, and
   the add button goes away with them: a row that cannot be edited is not a
   row anybody should be able to add next to. */
export function DeliverableRows({ value, onChange, disabled = false }: {
  value: Deliverable[];
  onChange: (next: Deliverable[]) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();

  function update(i: number, patch: Partial<Deliverable>) {
    onChange(value.map((d, idx) => (idx === i ? { ...d, ...patch } : d)));
  }

  /* Switching platform resets the type to that platform's first deliverable:
     keeping the old type would silently build an invalid pair (e.g. a TikTok
     "reel") that only surfaces as a 400 on submit. */
  function changePlatform(i: number, platform: string) {
    update(i, { platform, type: deliverablesFor(platform)[0] });
  }

  return (
    <>
      {value.map((d, i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 88px auto", gap: 8, marginBottom: 8 }}>
          <select className="select" value={d.platform} disabled={disabled}
            onChange={(e) => changePlatform(i, e.target.value)}>
            {SELLABLE_PLATFORMS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          <select className="select" value={d.type} disabled={disabled}
            onChange={(e) => update(i, { type: e.target.value })}>
            {deliverablesFor(d.platform).map((ty) => <option key={ty} value={ty}>{t(`deliverable.${ty}`, ty)}</option>)}
          </select>
          <select className="select" aria-label={t("profile.packageQuantity")} value={d.quantity} disabled={disabled}
            onChange={(e) => update(i, { quantity: Number(e.target.value) })}>
            {QUANTITIES.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <button type="button" className="btn btn-ghost" aria-label="remove"
            disabled={disabled || value.length === 1}
            onClick={() => onChange(value.filter((_, idx) => idx !== i))}>x</button>
        </div>
      ))}
      {!disabled && (
        <button type="button" className="btn btn-ghost" style={{ padding: "7px 13px", fontSize: 13 }}
          onClick={() => onChange([...value, emptyDeliverable()])}>
          + {t("campaign.addDeliverable")}
        </button>
      )}
    </>
  );
}
