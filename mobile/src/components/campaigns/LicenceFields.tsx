import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import {
  FIELDS,
  LICENCE_OPTIONS,
  draftIsComplete,
  isOptional,
  type LicenceDraft,
  type LicenceField,
  type LicenceOption,
} from "../../lib/licenceTerms";
import { ChoiceGroup, Field, Hint, type Choice } from "../ui";
import { colors, family, font, space } from "../../theme";
/* Side-effect import: registers the licence.* copy. Without it this section
   renders "licence.formTitle" at the reader. See lib/licenceStrings.ts. */
import "../../lib/licenceStrings";

/* The brand stating what it may do with the content, as a form.

   THE PRODUCT RULE THIS CONTROL EXISTS TO COMMUNICATE: the brand states the
   licence BEFORE the contract is created, and the creator reads that
   statement before accepting. Article 10 of the collaboration contract hands
   this clause to the Parties rather than to the platform, so Kolabo asks the
   question and writes down the answer; it does not pick a default and it does
   not check what it is told. formHint says that on screen and not only in
   this comment, because a brand that believes Kolabo vets the clause will
   write less than it means.

   NOTHING IS PRE-SELECTED. See EMPTY_DRAFT in lib/licenceTerms for why: a
   pre-selected option 2 would claim a paid-advertising licence from a brand
   that never read the question, and even a pre-selected option 1, safe as it
   is for the creator, would answer article 10 on the brand's behalf. The
   caller withholds its submit button until draftIsComplete passes, which is
   the one thing this component expects of it.

   THE FIELDS COME FROM FIELDS[option] rather than from a conditional here.
   The table in lib/licenceTerms is read by the render order, the completeness
   check and the request body at once, so an option whose fields change
   changes all three from one edit, and the sentence the creator eventually
   reads cannot describe a field this form stopped asking for.

   The key names are written out below rather than assembled from the field
   name. A key built from a value is a key no search finds, and somebody
   editing a label should be able to grep licence.lf_territories and land
   here. */

/* A guard against a pasted page, not a validation rule. The server is the
   authority on length and will answer licence_terms_invalid if it disagrees;
   this only stops a text field from quietly accepting something nobody meant
   to put in a contract. Generous because a territory list can legitimately
   name a dozen countries. */
const MAX_LENGTH = 500;

/* Two of the four are lists in practice, so they get the room to be written
   as one. A duration and a sum of money are each one line. */
const MULTILINE: LicenceField[] = ["licence_territories", "licence_media"];

const LABEL_KEY: Record<LicenceField, string> = {
  licence_duration: "licence.lf_duration",
  licence_territories: "licence.lf_territories",
  licence_media: "licence.lf_media",
  licence_consideration: "licence.lf_consideration",
};

const HINT_KEY: Record<LicenceField, string> = {
  licence_duration: "licence.lh_duration",
  licence_territories: "licence.lh_territories",
  licence_media: "licence.lh_media",
  licence_consideration: "licence.lh_consideration",
};

export function LicenceFields({
  value,
  onChange,
}: {
  value: LicenceDraft;
  onChange: (next: LicenceDraft) => void;
}) {
  const { t } = useTranslation();

  /* COPY AND ASSIGN rather than a computed property in a spread, the same
     call PartyDetailsSection makes and for the same reason: `field` is the
     LicenceField union rather than one literal, and how TypeScript types a
     computed key whose value is a union of literals has moved between
     versions. The unhappy outcome is an inferred string index signature that
     will not assign back to Record<LicenceField, string>, which on this app
     means a red CI run rather than a bug. An indexed write has nothing to
     infer. */
  function setField(field: LicenceField, text: string) {
    const next = { ...value.values };
    next[field] = text;
    onChange({ option: value.option, values: next });
  }

  /* ChoiceGroup hands back a bare string. The only values it can hand back
     are the three it was given, so the cast is safe here and nowhere else;
     optionOf is what narrows a value that came from the API. */
  function pick(option: string) {
    onChange({ option: option as LicenceOption, values: value.values });
  }

  const optionChoices: Choice[] = LICENCE_OPTIONS.map((option) => ({
    value: option,
    label: t(`licence.opt_${option}`),
    /* Three bare labels would leave a brand guessing which one lets it run an
       advert, which is the exact reading the copy exists to prevent. */
    description: t(`licence.desc_${option}`),
  }));

  const chosen = value.option === "" ? null : value.option;
  const asked = chosen ? FIELDS[chosen] : [];

  return (
    <View>
      <Text style={styles.legend}>{t("licence.formTitle")}</Text>
      {/* ABOVE the question, not under the submit button. Somebody who reads
          one sentence in this section has to read this one: what they write
          goes on the contract word for word, the creator reads it before
          accepting, and Kolabo does not check it. Under the button it would
          be a disclaimer; here it is what the section is for. */}
      <Hint>{t("licence.formHint")}</Hint>
      <Hint>{t("licence.pricing")}</Hint>

      <View style={{ height: space(3) }} />
      <Text style={styles.groupLabel}>{t("licence.optionLabel")}</Text>
      <ChoiceGroup options={optionChoices} value={value.option} onChange={pick} />
      {/* Directly under the chips, because this is where the reader decides,
          and because an empty chip row reads as a control that failed to load
          rather than as a question waiting for an answer. */}
      {chosen === null ? <Hint>{t("licence.chooseFirst")}</Hint> : null}

      {asked.length > 0 ? (
        <View>
          <View style={{ height: space(4) }} />
          {asked.map((field) => {
            const optional = chosen !== null && isOptional(chosen, field);
            const base = t(LABEL_KEY[field]);
            const label = optional ? `${base} (${t("licence.optional")})` : base;
            const multiline = MULTILINE.includes(field);
            return (
              <Field
                key={field}
                label={label}
                value={value.values[field]}
                onChangeText={(text) => setField(field, text)}
                hint={t(HINT_KEY[field])}
                multiline={multiline}
                numberOfLines={multiline ? 3 : undefined}
                maxLength={MAX_LENGTH}
              />
            );
          })}
          {/* Last, because it is about what happens to the words above rather
              than about any one field: they travel into the contract in the
              language they were typed in, and nothing translates them. */}
          <Hint>{t("licence.verbatim")}</Hint>
          {!draftIsComplete(value) ? <Hint>{t("licence.incompleteForm")}</Hint> : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  /* Matches TargetingFields, the other section of this form that draws its
     own heading. */
  legend: { fontSize: font.small, fontFamily: family.bodyBold, color: colors.ink, marginBottom: space(1.5) },
  groupLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) },
});
