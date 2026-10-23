import { useTranslation } from "react-i18next";
import { COUNTRIES } from "../lib/countries";
import { PARTY_FIELDS } from "../lib/party";
import type { PartyDetails } from "../lib/types";

/* THE PARTIES TO A CONTRACT, as each of them stated themselves.

   WHO MAY READ THIS IS DECIDED BY THE SERVER AND NOT HERE. The two snapshots
   ride on GET /contracts/{id}, which refuses anybody who is not a party with
   contract_not_a_party, so a reader holding this data is already a party or an
   admin. What this component owns is the other half of that rule: it is
   imported by pages/ContractPage.tsx and by nothing else, and the party block
   appears on no public surface. lib/types.ts carries the matching note on
   PublicProfile and SearchResult, which must never gain a party field.

   NOTHING HERE IS VERIFIED. party.contractSub says so above the blocks, on the
   screen where somebody is about to put their name under them. The block exists
   because a generated contract used to identify its parties by user id alone,
   so a typed signature validated against nothing; it does not exist to vouch
   for anybody. There is no tick, no badge and nothing coloured to read as
   approval, and adding one would turn a declaration into a credential. */

/* One stated field. STACKED RATHER THAN THE CONTRACT PAGE'S LEFT/RIGHT Row,
   for two reasons: an address has line breaks in it and a right-aligned
   multi-line value reads as ragged, and a registered name plus a label does
   not fit on one phone-width line. pre-wrap keeps the address as the party
   typed it, which is also how it is printed on the contract. */
function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: "3px 0" }}>
      <span className="muted" style={{ fontSize: 12.5 }}>{label}</span>
      <div style={{ fontSize: 13.5, whiteSpace: "pre-wrap" }}>{value}</div>
    </div>
  );
}

/* English in both languages, like every other country droplist and label on
   web; mobile localises the same codes. Fix the two together. The raw code is
   the fallback rather than an empty space: a block written against a country
   lib/countries.ts has not caught up with should degrade to ugly, not to a
   contract party with no country on it. */
function countryLabel(code: string): string {
  return COUNTRIES.find((c) => c.code === code)?.name || code;
}

function PartyBlock({ heading, details }: { heading: string; details: PartyDetails | null }) {
  const { t } = useTranslation();

  if (!details) {
    return (
      <div>
        <span className="label">{heading}</span>
        <p className="muted" style={{ fontSize: 13.5, margin: "2px 0 0" }}>{t("party.sideMissing")}</p>
      </div>
    );
  }

  /* A party_type this build has not heard of still renders its name and its
     type, and simply lists no detail rows. Same reasoning as an unrecognised
     social account status: a value the client does not know should degrade to
     less information rather than to a blank screen on the page a signature
     happens on. */
  const fields = PARTY_FIELDS[details.party_type] ?? [];

  return (
    <div>
      <span className="label">{heading}</span>
      {/* display_label is the server's derived name for this party. It is the
          heading of the block for the reason it exists: one field to read
          without branching on the type. */}
      <div style={{ fontWeight: 600, fontSize: 15 }}>{details.display_label}</div>
      <div className="muted" style={{ fontSize: 13 }}>{t(`party.type_${details.party_type}`)}</div>
      <div style={{ marginTop: 6 }}>
        {fields
          /* legal_name is what display_label was derived from, so printing it
             again under a label would say the same thing twice. */
          .filter((field) => field.name !== "legal_name")
          .map((field) => {
            const raw = details[field.name];
            const value = typeof raw === "string" ? raw.trim() : "";
            /* AN ABSENT FIELD PRINTS NOTHING AT ALL. The shape varies by type,
               so a missing registration number on a sole_trader block is the
               normal state and not an omission; an empty row under its heading
               would read as something withheld. */
            if (!value) return null;
            return (
              <Detail
                key={field.name}
                label={t(`party.${field.labelKey}`)}
                value={field.name === "country" ? countryLabel(value) : value}
              />
            );
          })}
      </div>
    </div>
  );
}

export function ContractParties({
  business,
  influencer
}: {
  business: PartyDetails | null;
  influencer: PartyDetails | null;
}) {
  const { t } = useTranslation();
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("party.contractTitle")}</h3>
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t("party.contractSub")}</p>
      {!business && !influencer ? (
        /* NEITHER BLOCK MEANS AN OLD CONTRACT rather than two parties who
           failed to fill something in. Every contract generated from now on
           carries both snapshots, because generation refuses without them, so
           one way to see this is to open a contract written before the blocks
           existed, which has nothing to backfill from beyond a pair of user
           ids. It says so, and points at the document below, where those ids
           still are.

           FALSY RATHER THAN `=== null`, AND THAT IS THE OTHER WAY TO GET HERE.
           ContractDetailOut in backend/app/modules/contracts/schemas.py is
           still ContractOut plus `body`: the columns exist, the detail response
           does not carry them yet, so both fields arrive UNDEFINED. A strict
           null test would fall through to two blocks each saying the party had
           not filled their details in, which is the one sentence on this card
           that would be untrue. Null and absent produce the same card, which
           is what a reader needs either way. */
        <p className="muted" style={{ fontSize: 13.5, marginBottom: 0 }}>{t("party.legacy")}</p>
      ) : (
        <div style={{ display: "grid", gap: 16 }}>
          {/* The buyer first, in the order the contract itself names them. */}
          <PartyBlock heading={t("party.sideBusiness")} details={business} />
          <PartyBlock heading={t("party.sideCreator")} details={influencer} />
        </div>
      )}
    </div>
  );
}
