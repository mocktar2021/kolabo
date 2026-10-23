import { useTranslation } from "react-i18next";
import {
  LICENCE_FIELDS,
  LICENCE_OPTIONS,
  licenceIsComplete,
  type LicenceDraft,
  type LicenceOption
} from "../lib/licence";

/* WHAT THE BRAND MAY DO WITH THE CONTENT, as a form.

   WHY THIS IS A CONTROL AND NOT A SCREEN. The licence is part of the terms, so
   it is stated wherever the rest of the terms are stated: on the campaign form
   and in the direct order flow. A screen of its own would be a fourth step
   between writing a brief and publishing it, and the thing it asks about is one
   radio group and at most three boxes. One component for both call sites for
   the same reason components/TargetingFields.tsx is one for its two: the
   question is identical and a second copy would drift within a month.

   THE OPTION IS CHOSEN FIRST AND DECIDES THE REST, which is the pattern
   pages/PartyDetails.tsx established for the form of party and the reason the
   further fields are hidden until it is answered. There is NO DEFAULT OPTION,
   and that is load-bearing rather than tidy: a default would both show the
   wrong fields and nominate a normal case, and here nominating a normal case
   nominates a price. lib/licence.ts holds the field map; nothing about which
   field belongs to which option is decided in this file.

   THE THREE GET IDENTICAL TREATMENT AND ARE NOT CALLED EQUAL. Same control,
   same weight, a description each, no ordering cue and no option marked as the
   usual one. That much is copied from the party form. What is NOT copied is its
   equalForms sentence: the three forms of party really are equal on Kolabo,
   while these three are three different bargains at three different prices, and
   licence.priceNote says so instead. See the note at the top of
   lib/licenceStrings.ts.

   EVERY DESCRIPTION HERE IS ADDRESSED TO THE BRAND. licence.optionDesc_* is the
   second person voice, "you may run it"; the creator reads licence.creatorDesc_*
   on their own screens, which says the same fact from the other side of it.
   Using one set for both would tell a creator they may advertise with rights
   they are granting away, which is the opposite of the truth on the screen
   where it costs the most. */
export function LicenceFields({
  idPrefix,
  value,
  onChange,
  disabled = false
}: {
  /* Prefixes the input ids AND the radio group's name. The name matters: two
     licence controls on one page with the same radio name would behave as one
     group, and the cart renders a basket. */
  idPrefix: string;
  value: LicenceDraft;
  onChange: (next: LicenceDraft) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();

  function choose(option: LicenceOption) {
    /* The typed values are deliberately kept across a change of option. Period
       and territories belong to options 2 and 3 alike, and retyping a territory
       list because somebody moved from a licence to an assignment is how a form
       gets abandoned halfway. licenceBody is what makes sure the fields of the
       option NOT chosen never reach the server. */
    onChange({ ...value, option });
  }

  function setField(name: string, next: string) {
    onChange({ ...value, values: { ...value.values, [name]: next } });
  }

  const fields = value.option === null ? [] : LICENCE_FIELDS[value.option];
  const complete = licenceIsComplete(value);

  return (
    <>
      <div className="field">
        <span className="label">{t("licence.legend")}</span>
        {/* The decision said out loud, before the clause is named. A brand that
            reads "licence de rediffusion" and picks it because it sounds
            thorough has not made a decision, it has guessed. */}
        <p className="muted" style={{ fontSize: 13, margin: "0 0 6px" }}>{t("licence.explain")}</p>
        {/* Why it is being asked now rather than at signature: the creator
            prices against it. Said before the choice, not after it. */}
        <p className="muted" style={{ fontSize: 13, margin: "0 0 10px" }}>{t("licence.printed")}</p>

        <span className="label" style={{ fontSize: 13, display: "block" }}>{t("licence.question")}</span>
        <div style={{ display: "grid", gap: 10, marginTop: 4 }}>
          {LICENCE_OPTIONS.map((option) => (
            <label
              key={option}
              style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: "pointer" }}
            >
              <input
                type="radio"
                name={`${idPrefix}-licence-option`}
                value={option}
                checked={value.option === option}
                disabled={disabled}
                style={{ marginTop: 3 }}
                onChange={() => choose(option)}
              />
              <span>
                <span style={{ fontWeight: 600, fontSize: 14.5 }}>{t(`licence.name_${option}`)}</span>
                <span className="muted" style={{ display: "block", fontSize: 13 }}>
                  {t(`licence.optionDesc_${option}`)}
                </span>
              </span>
            </label>
          ))}
        </div>
        <div className="hint">{t("licence.priceNote")}</div>
      </div>

      {/* Option 1 asks for nothing further, so nothing further is drawn: there
          is no period to state because nothing is licensed and no territory
          because nothing is run anywhere. An empty field list is a real answer
          here rather than a branch that was forgotten. */}
      {fields.map((field) => (
        <div className="field" key={field.name}>
          <label className="label" htmlFor={`${idPrefix}-${field.name}`}>
            {t(`licence.${field.labelKey}`)}
          </label>
          {/* A TEXTAREA FOR THE TWO FIELDS THAT HOLD LISTS. Territories and
              media are usually several things ("Benin, Togo, Cote d'Ivoire";
              "our social accounts, our site, in store displays"), and a
              single-line box tells somebody to name one. The period and the
              separate payment are one clause each. Same branch-on-the-name
              shape pages/PartyDetails.tsx uses for the address, and for the
              same reason: the value is printed on the contract as written. */}
          {field.name === "licence_territories" || field.name === "licence_media" ? (
            <textarea
              id={`${idPrefix}-${field.name}`}
              className="input"
              rows={2}
              style={{ resize: "vertical" }}
              value={value.values[field.name] ?? ""}
              disabled={disabled}
              onChange={(e) => setField(field.name, e.target.value)}
            />
          ) : (
            <input
              id={`${idPrefix}-${field.name}`}
              className="input"
              value={value.values[field.name] ?? ""}
              disabled={disabled}
              onChange={(e) => setField(field.name, e.target.value)}
            />
          )}
          <div className="hint">{t(`licence.${field.hintKey}`)}</div>
        </div>
      ))}

      {/* Said once, under the boxes it is about: these are not droplists and
          they are not going to be. A stated value is printed into the contract
          verbatim and is never translated, so "monde entier" stays "monde
          entier" on an English contract and vice versa. */}
      {fields.length > 0 && (
        <p className="muted" style={{ fontSize: 13, margin: "-6px 0 14px" }}>{t("licence.freeText")}</p>
      )}

      {/* WHAT IS STILL MISSING, SAID HERE RATHER THAN AT EACH BUTTON. Both call
          sites disable their own submit on licenceIsComplete, and both would
          otherwise have to carry their own copy of these two sentences. The
          server refuses an incomplete statement with licence_terms_invalid, and
          arriving at that after a brief has been written is worse than being
          told now. */}
      {value.option === null ? (
        <div className="hint" style={{ marginTop: -6, marginBottom: 14 }}>{t("licence.chooseFirst")}</div>
      ) : !complete ? (
        <div className="hint" style={{ marginTop: -6, marginBottom: 14 }}>{t("licence.incomplete")}</div>
      ) : null}
    </>
  );
}
