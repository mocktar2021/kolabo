import { useTranslation } from "react-i18next";
import { NO_FILTER, isFiltered, type StatementFilter, type StatementOptions } from "../lib/statement";

/* The filter row above a money statement, identical on both sides of the
   escrow.

   ONE COMPONENT FOR BOTH SCREENS because it is one question asked twice. The
   only thing that genuinely differs is what the other party is called — a
   creator's counterparty is a client, a buyer's is a creator — so that label
   arrives as a prop rather than as a role check inside here.

   EVERY DROPLIST IS OFFERED ONLY WHEN IT HAS SOMETHING TO CHOOSE BETWEEN. A
   filter over a single campaign is a control whose only possible outcome is
   the page it is already on, and a row of them is how a screen starts looking
   like an admin console. The same rule the year selector has always followed.

   The clear button appears the moment anything is set and restores the
   unfiltered view in one click, including the period, which is the half that
   costs a request. Somebody who narrowed to a week in March must never have
   to remember which four controls they touched to get back. */
export function StatementFilters({
  idPrefix,
  value,
  onChange,
  options,
  counterpartyLabel,
  counterpartyAll
}: {
  idPrefix: string;
  value: StatementFilter;
  onChange: (next: StatementFilter) => void;
  options: StatementOptions;
  counterpartyLabel: string;
  counterpartyAll: string;
}) {
  const { t } = useTranslation();

  return (
    <div className="card" style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
      {/* Both bounds are INCLUSIVE server-side: they name days somebody picked
          off a calendar, and a range whose last day is not in it is the kind
          of off-by-one nobody reports and everybody works around. An INVERTED
          range is not an error either — it matches nothing and the screen
          honestly answers zero, which is the true reading of "between the 5th
          and the 1st". */}
      <div>
        <label className="label" htmlFor={`${idPrefix}-from`}>{t("filt.from")}</label>
        <input id={`${idPrefix}-from`} className="input" type="date" value={value.from}
          onChange={(e) => onChange({ ...value, from: e.target.value })} />
      </div>
      <div>
        <label className="label" htmlFor={`${idPrefix}-to`}>{t("filt.to")}</label>
        <input id={`${idPrefix}-to`} className="input" type="date" value={value.to}
          onChange={(e) => onChange({ ...value, to: e.target.value })} />
      </div>

      {options.years.length > 1 && (
        <div>
          <label className="label" htmlFor={`${idPrefix}-year`}>{t("filt.year")}</label>
          <select id={`${idPrefix}-year`} className="select" value={value.year === null ? "" : String(value.year)}
            onChange={(e) => onChange({ ...value, year: e.target.value === "" ? null : Number(e.target.value) })}>
            <option value="">{t("filt.yearAll")}</option>
            {options.years.map((y) => <option key={y} value={String(y)}>{y}</option>)}
          </select>
        </div>
      )}

      {options.campaigns.length > 1 && (
        <div>
          <label className="label" htmlFor={`${idPrefix}-campaign`}>{t("filt.campaign")}</label>
          <select id={`${idPrefix}-campaign`} className="select" value={value.campaign}
            onChange={(e) => onChange({ ...value, campaign: e.target.value })}>
            <option value="">{t("filt.campaignAll")}</option>
            {options.campaigns.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      )}

      {options.counterparties.length > 1 && (
        <div>
          <label className="label" htmlFor={`${idPrefix}-counterparty`}>{counterpartyLabel}</label>
          <select id={`${idPrefix}-counterparty`} className="select" value={value.counterparty}
            onChange={(e) => onChange({ ...value, counterparty: e.target.value })}>
            <option value="">{counterpartyAll}</option>
            {options.counterparties.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      )}

      {isFiltered(value) && (
        <button type="button" className="btn btn-ghost" onClick={() => onChange(NO_FILTER)}>
          {t("filt.clear")}
        </button>
      )}
    </div>
  );
}
