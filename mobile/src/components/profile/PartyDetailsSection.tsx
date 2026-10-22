import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { COUNTRIES, countryName } from "../../lib/countries";
import {
  EMPTY_VALUES,
  FIELDS,
  PARTY_TYPES,
  isComplete,
  isOptional,
  toPayload,
  valuesFrom,
  type PartyDetails,
  type PartyField,
  type PartyType,
  type PartyValues,
} from "../../lib/partyDetails";
import {
  Banner,
  ChoiceGroup,
  Field,
  Hint,
  PrimaryButton,
  SectionTitle,
  Select,
  type Choice,
} from "../ui";
import { colors, family, font, space } from "../../theme";
/* Side-effect import: registers the party.* copy on the i18n instance. Without
   it this card renders "party.title" at the reader. Same arrangement the
   package and payment sections use; see lib/partyStrings.ts for why the keys
   live outside strings.ts. */
import "../../lib/partyStrings";

/* The one field that is a paragraph rather than a line. An address in these
   markets is often a landmark, a quarter and a city rather than a street
   number, so it needs the room to be written the way it would be said. */
const MULTILINE: PartyField[] = ["address"];

/* legal_name means three different things depending on the type: a company's
   registered name, a natural person's own name, an association's name. Try the
   type-specific key, fall back to the generic one, so only the fields that
   need an override carry one in partyStrings. */
function labelKey(field: PartyField, type: PartyType): string {
  return `party.f_${field}_${type}`;
}

export function PartyDetailsSection({
  token,
  defaultType,
  onSaved,
}: {
  token: string | null;
  /* Pre-selected when nothing is saved yet. The endpoint is /profiles/me and
     the backend reads the side off the token, so this is the only thing the
     component needs from its caller: a creator should open on their own name
     and a business on a registered company, rather than each being handed the
     other's form to read first. */
  defaultType: PartyType;
  onSaved?: () => void | Promise<void>;
}) {
  const { t, i18n } = useTranslation();
  const [type, setType] = useState<PartyType>(defaultType);
  const [values, setValues] = useState<PartyValues>({ ...EMPTY_VALUES });
  /* Whether the API already holds a block. Drives two things and nothing else:
     the "nothing saved yet" hint, and whether the immutability warning under
     the type chips is worth showing. */
  const [stored, setStored] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const details = await api<PartyDetails>("/profiles/me/party-details", { token });
      setType(details.party_type);
      setValues(valuesFrom(details));
      setStored(true);
    } catch (e) {
      /* 404 means no block yet, and a blank form is the right state for that,
         exactly as the two profile screens treat a missing profile. Anything
         else is worth saying, because a party block that failed to load would
         otherwise look identical to one that was never filled in, and the
         reader would retype what is already stored. */
      if (e instanceof ApiError && e.status === 404) {
        setStored(false);
        return;
      }
      setError(errorText(e, t));
    }
  }, [token, t]);

  useEffect(() => {
    void load();
  }, [load]);

  /* COPY AND ASSIGN rather than `{ ...prev, [field]: value }`. `field` is the
     PartyField union, not one literal, and how TypeScript types a computed
     property whose key is a union of literals has moved between versions: the
     unhappy outcome is an inferred string index signature that will not assign
     back to Record<PartyField, string>, which on this app means a red CI run
     rather than a bug. An indexed write has nothing to infer. */
  function set(field: PartyField, value: string) {
    setValues((prev) => {
      const next = { ...prev };
      next[field] = value;
      return next;
    });
    /* A success banner that outlives the next keystroke is a lie about the
       current state of the form. */
    setSaved(false);
  }

  async function save() {
    if (!isComplete(type, values)) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      /* toPayload is the only thing that builds this body: it drops
         display_label, which the server derives, and drops any field belonging
         to a type the reader has since switched away from. */
      await api("/profiles/me/party-details", { method: "PUT", token, body: toPayload(type, values) });
      setStored(true);
      setSaved(true);
      /* The go-live checklist upstairs may come to count this block. Reloading
         it costs one request on a deliberate tap. */
      if (onSaved) await onSaved();
    } catch (e) {
      /* INLINE, not in the screen's top-level banner. On the creator screen
         this card sits below the avatar, the bio, the categories and the
         socials, so a refusal reported at the top of the screen is several
         screens above the button that was pressed. */
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  const typeOptions: Choice[] = PARTY_TYPES.map((value) => ({
    value,
    label: t(`party.type_${value}`),
    /* Three bare labels would leave an unregistered trader guessing which one
       is theirs, which is the exact reading the copy exists to prevent. */
    description: t(`party.desc_${value}`),
  }));

  /* Localized country names, per lib/countries.countryName. KNOWN DIVERGENCE,
     recorded rather than accidental: the same droplist on web is English only.
     Mobile follows mobile, and every other country picker in this app
     (CreatorProfileScreen, registration) already reads this way, so matching
     web here would have made this one list the odd one out on the phone. */
  const countryOptions: Choice[] = COUNTRIES.map((c) => ({
    value: c.code,
    label: countryName(c, i18n.language),
  }));

  const complete = isComplete(type, values);

  return (
    <View>
      <SectionTitle>{t("party.title")}</SectionTitle>
      {/* ABOVE the form, not under the Save button. Somebody who reads one
          sentence on this card has to read this one: what they write here goes
          on a contract, and Kolabo does not check it. Under the button it
          would be a disclaimer; here it is what the form is for. */}
      <Hint>{t("party.hint")}</Hint>
      {error ? (
        <View style={{ marginTop: space(2) }}>
          <Banner kind="error">{error}</Banner>
        </View>
      ) : null}
      {saved ? (
        <View style={{ marginTop: space(2) }}>
          <Banner kind="success">{t("party.saved")}</Banner>
        </View>
      ) : null}
      {!stored ? (
        <View style={{ marginTop: space(2) }}>
          <Banner kind="info">{t("party.none")}</Banner>
        </View>
      ) : null}

      <View style={{ height: space(3) }} />
      <Text style={styles.fieldLabel}>{t("party.typeLabel")}</Text>
      <ChoiceGroup options={typeOptions} value={type} onChange={(v) => setType(v as PartyType)} />
      {/* Directly under the chips, because this is where the reader decides.
          Registered company is offered first as the commonest answer on the
          business side, and first in a list reads as expected unless something
          says otherwise. */}
      <Hint>{t("party.openToAll")}</Hint>
      {/* Said before a contract exists rather than after. Nothing in the GET
          reports whether one does, so the alternative would have been to lock
          the chips on a guess; if the server refuses, party_type_immutable
          arrives already translated and names the same next step. */}
      {stored ? <Hint>{t("party.typeLocked")}</Hint> : null}

      <View style={{ height: space(4) }} />
      {FIELDS[type].map((field) => {
        const optional = isOptional(type, field);
        const base = t(labelKey(field, type), { defaultValue: t(`party.f_${field}`) });
        const label = optional ? `${base} (${t("party.optional")})` : base;
        const hint =
          t(`party.h_${field}_${type}`, { defaultValue: "" }) ||
          t(`party.h_${field}`, { defaultValue: "" }) ||
          undefined;

        if (field === "country") {
          return (
            <Select
              key={field}
              label={label}
              value={values.country}
              options={countryOptions}
              onChange={(v) => set("country", v)}
              placeholder={t("party.country_placeholder")}
              hint={hint}
            />
          );
        }

        const multiline = MULTILINE.includes(field);
        return (
          <Field
            key={field}
            label={label}
            value={values[field]}
            onChangeText={(v) => set(field, v)}
            hint={hint}
            multiline={multiline}
            numberOfLines={multiline ? 3 : undefined}
            maxLength={240}
          />
        );
      })}

      {!complete ? <Hint>{t("party.incomplete")}</Hint> : null}
      <View style={{ height: space(2) }} />
      <PrimaryButton
        title={busy ? t("common.working") : t("party.save")}
        onPress={() => void save()}
        loading={busy}
        disabled={!complete}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  /* Matches the label the other profile sections put above a ChoiceGroup,
     which ui.Field draws for its own inputs but a bare chip row does not. */
  fieldLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) },
});
