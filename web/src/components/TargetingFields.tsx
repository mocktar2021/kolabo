import { useTranslation } from "react-i18next";
import { CATEGORIES } from "../lib/categories";
import { COUNTRIES } from "../lib/countries";

/* Who a brand is hoping to reach with a brief, as a form.

   THE PRODUCT RULE THIS CONTROL EXISTS TO COMMUNICATE, and the reason every
   label here says "cible" and never "exigences": TARGETING RANKS, IT DOES NOT
   EXCLUDE. A creator who matches sees the brief first; ANY signed-in creator
   may apply to ANY open brief, and nothing set here removes a row from
   anybody's board. backend/app/modules/campaigns/board.py is the authority
   and says why at length — briefly, on a pilot roster a hard filter shows
   most creators an empty board, and a board that is empty twice is a board
   nobody opens a third time. The asymmetry settles it: declining an
   application the brand did not want costs one click, while the application
   it never saw costs it the creator.

   That rule is stated ON SCREEN and not only here, because a brand that
   believes it set a hard filter will read an off-target application as a bug
   in our matching and decline it unread — which is the exact outcome the soft
   filter exists to avoid.

   ONE COMPONENT FOR CREATE AND EDIT. The fields are identical on both and
   they are NOT part of the lock that freezes budget, deliverables and
   deadline once a creator has bid: nobody prices a brief against who else
   the brand hoped to hear from, so widening the board or closing it to new
   applications takes nothing away from the offers already on the table.
   campaigns/editing.py keeps them out of LOCKED_FIELDS for that reason. */

export type Targeting = {
  is_open: boolean;
  categories: string[];
  countries: string[];
  /* Held as strings, not numbers. An empty box means "no bound", and a number
     state cannot hold that without inventing a zero — which is a real value
     here: the server takes ge=0, because the floor of "up to 5000" is zero
     followers rather than one. */
  minFollowers: string;
  maxFollowers: string;
};

export const EMPTY_TARGETING: Targeting = {
  is_open: false,
  categories: [],
  countries: [],
  minFollowers: "",
  maxFollowers: ""
};

/* The four targeting columns as they travel on a campaign, in and out. */
export type TargetingBody = {
  is_open: boolean;
  target_categories: string[];
  target_countries: string[];
  target_min_followers: number | null;
  target_max_followers: number | null;
};

export function targetingOf(campaign: TargetingBody): Targeting {
  return {
    is_open: campaign.is_open,
    categories: campaign.target_categories ?? [],
    countries: campaign.target_countries ?? [],
    minFollowers: campaign.target_min_followers === null ? "" : String(campaign.target_min_followers),
    maxFollowers: campaign.target_max_followers === null ? "" : String(campaign.target_max_followers)
  };
}

export function targetingBody(value: Targeting): TargetingBody {
  return {
    is_open: value.is_open,
    target_categories: value.categories,
    target_countries: value.countries,
    /* An empty box is null and not zero. Zero is a bound the brand did not
       set, and sending it would quietly exclude every creator whose audience
       we do not know from the top of their own board. */
    target_min_followers: value.minFollowers === "" ? null : Number(value.minFollowers),
    target_max_followers: value.maxFollowers === "" ? null : Number(value.maxFollowers)
  };
}

/* A multi-select as toggle chips rather than a <select multiple>, which on a
   phone is a scrolling box nobody can operate with one thumb. Each chip is a
   real checkbox inside its label, so the whole thing is keyboard reachable
   and screen-reader correct without any ARIA of its own. */
function ChipPicker({ options, selected, onToggle }: {
  options: { value: string; label: string }[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {options.map((o) => {
        const on = selected.includes(o.value);
        return (
          <label
            key={o.value}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer",
              fontSize: 13.5, padding: "5px 10px", borderRadius: 999,
              border: `1px solid ${on ? "var(--indigo)" : "var(--line)"}`,
              background: on ? "var(--surface-2)" : "transparent"
            }}
          >
            <input type="checkbox" checked={on} onChange={() => onToggle(o.value)} style={{ margin: 0 }} />
            {o.label}
          </label>
        );
      })}
    </div>
  );
}

export function TargetingFields({ idPrefix, value, onChange }: {
  idPrefix: string;
  value: Targeting;
  onChange: (next: Targeting) => void;
}) {
  const { t } = useTranslation();

  function toggle(key: "categories" | "countries", entry: string) {
    const current = value[key];
    onChange({
      ...value,
      [key]: current.includes(entry) ? current.filter((c) => c !== entry) : [...current, entry]
    });
  }

  return (
    <>
      <div className="field">
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
          <input type="checkbox" checked={value.is_open}
            onChange={(e) => onChange({ ...value, is_open: e.target.checked })} />
          {t("target.open")}
        </label>
        <p className="muted" style={{ fontSize: 13, margin: "6px 0 0" }}>{t("target.openHint")}</p>
      </div>

      <div className="field">
        <span className="label">{t("target.legend")}</span>
        {/* The rule, on screen. See the note at the top of this file: a brand
            that thinks it set a hard filter declines off-target applications
            unread. */}
        <p className="muted" style={{ fontSize: 13, margin: "0 0 10px" }}>{t("target.explain")}</p>

        <span className="label" style={{ fontSize: 13 }}>{t("target.categories")}</span>
        <ChipPicker
          options={CATEGORIES.map((c) => ({ value: c, label: t(`cat.${c}`) }))}
          selected={value.categories}
          onToggle={(c) => toggle("categories", c)}
        />

        <span className="label" style={{ fontSize: 13, marginTop: 12, display: "block" }}>{t("target.countries")}</span>
        <ChipPicker
          options={COUNTRIES.map((c) => ({ value: c.code, label: c.name }))}
          selected={value.countries}
          onToggle={(c) => toggle("countries", c)}
        />
      </div>

      <div className="field" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <label className="label" htmlFor={`${idPrefix}-min-followers`}>{t("target.minFollowers")}</label>
          <input id={`${idPrefix}-min-followers`} className="input" inputMode="numeric" value={value.minFollowers}
            onChange={(e) => onChange({ ...value, minFollowers: e.target.value.replace(/\D/g, "") })}
            placeholder="5000" />
        </div>
        <div>
          <label className="label" htmlFor={`${idPrefix}-max-followers`}>{t("target.maxFollowers")}</label>
          <input id={`${idPrefix}-max-followers`} className="input" inputMode="numeric" value={value.maxFollowers}
            onChange={(e) => onChange({ ...value, maxFollowers: e.target.value.replace(/\D/g, "") })}
            placeholder="100000" />
        </div>
      </div>
      <p className="muted" style={{ fontSize: 13, margin: "-6px 0 14px" }}>{t("target.followersHint")}</p>
    </>
  );
}
