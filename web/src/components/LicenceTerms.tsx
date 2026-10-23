import { useTranslation } from "react-i18next";
import { licenceRows, statedLicence, type LicenceCarrier } from "../lib/licence";

/* WHAT THE BRAND SAID IT MAY DO WITH THE CONTENT, read-only.

   THE REQUIREMENT THIS COMPONENT IS. A creator prices option 2 differently from
   option 1: one is a post on their own account, the other is a paid
   advertisement a brand may run for a year. So the licence has to be on screen
   BEFORE the creator accepts, everywhere a creator decides, which today is
   three places: a brief on the open board, an invitation, and a direct order.
   The first two are pages/Board.tsx and pages/MyInvitations.tsx; the third is
   the same invitation card, because a direct order reaches a creator as an
   invitation row carrying a live offer. It is also on pages/ContractPage.tsx,
   beside the party blocks, which is the one surface both parties read.

   A creator shown the rate and the timeline but not the licence is being asked
   to price a job whose scope they cannot see. That is the whole reason this
   exists, and a future change that drops it from any of those screens puts them
   back there.

   TWO VOICES, PICKED BY THE CALLER AND NOT GUESSED HERE.

     voice="creator"  the board and the invitations page. licence.creatorDesc_*
                      is the second person from the creator's side: "the brand
                      will be able to run your content". Followed by
                      licence.creatorPrice, because the next thing that happens
                      on both of those screens is a number being typed.

     voice="parties"  the contract page, which both parties and admins read.
                      licence.partiesDesc_* names both sides in the third
                      person, because there is no "you" that is true for every
                      reader of it.

   The brand's own form uses a third set, licence.optionDesc_*, and none of the
   three may be reused for another reader. See the note at the top of
   lib/licenceStrings.ts: a creator told "you may run it as a paid
   advertisement" about rights they are GRANTING has been told the opposite of
   the truth.

   NOTHING HERE IS A VERDICT ON THE LICENCE, and the copy must stay that way.
   Kolabo records what the brand stated and prints it; it does not advise a
   creator whether to accept it, and it does not mark an option as generous or
   mean. licence.creatorPrice is the strongest thing said on these screens and
   it only says that the options differ in price, which they do. */
export function LicenceTerms({
  row,
  voice,
  framed = false
}: {
  /* Any payload that may carry the five fields: a campaign, an open brief, the
     campaign nested on an invitation, a contract. Every field of LicenceCarrier
     is optional, so a caller hands over whatever it already holds and a backend
     that is not sending them yet renders the "not stated" sentence rather than
     failing to compile. See lib/licence.ts. */
  row: LicenceCarrier | null | undefined;
  voice: "creator" | "parties";
  /* A card of its own, or a section inside somebody else's card. The contract
     page wants the first, beside the party blocks; a brief card and an
     invitation card want the second, because the licence is part of the terms
     on that card rather than a separate object. */
  framed?: boolean;
}) {
  const { t } = useTranslation();
  const licence = statedLicence(row);

  const sub = voice === "creator" ? t("licence.creatorSub") : t("licence.partiesSub");
  const missing = voice === "creator" ? t("licence.missingBrief") : t("licence.missingContract");

  const body = (
    <>
      {licence === null ? (
        /* NOTHING STATED IS AN ORDINARY STATE AND NOT AN ERROR, so it is muted
           copy and not an alert. Every brief and every contract written before
           this was captured is in it, and there is nothing to backfill from.
           What to do about it differs by screen, which is why the sentence
           does: a creator looking at a brief should ask the brand before
           accepting, while a contract already generated has its own article 10
           in the document below it. */
        <p className="muted" style={{ fontSize: 13.5, margin: "6px 0 0" }}>{missing}</p>
      ) : (
        <>
          {licence.known !== null ? (
            <>
              <div style={{ fontWeight: 600, fontSize: 14.5, marginTop: 6 }}>
                {t(`licence.name_${licence.known}`)}
              </div>
              <p style={{ fontSize: 13.5, margin: "4px 0 0" }}>
                {t(`licence.${voice}Desc_${licence.known}`)}
              </p>
            </>
          ) : (
            /* AN OPTION THIS BUILD HAS NEVER HEARD OF still prints its stated
               values below, because the brand wrote them and the other side has
               to be able to read them. What is withheld is the plain-language
               sentence, because this build cannot vouch for what a fourth
               option means. Same defence as an unrecognised party_type in
               components/ContractParties.tsx: on a screen where somebody is
               about to agree to something, printing less beats printing a
               confident guess. */
            <>
              <div style={{ fontWeight: 600, fontSize: 14.5, marginTop: 6 }}>
                {t("licence.optionLabel")} {licence.option}
              </div>
              <p className="muted" style={{ fontSize: 13.5, margin: "4px 0 0" }}>
                {t("licence.unknownOption", { option: licence.option })}
              </p>
            </>
          )}

          {/* The limits the brand stated, in article 10's own order.

              AN ABSENT VALUE PRINTS NOTHING AT ALL. Option 1 states none of
              these and option 3 states no media, so a missing row is the normal
              shape of that option rather than something withheld, and an empty
              row under its heading would read as a blank the brand left. Same
              rule the party blocks follow.

              pre-wrap because the value is printed on the contract as the brand
              typed it, line breaks included: a list of territories written one
              per line stays one per line here. */}
          <div style={{ marginTop: 8 }}>
            {licenceRows(licence).map((field) => {
              const value = licence.values[field.name];
              if (value === null) return null;
              return (
                <div key={field.name} style={{ padding: "3px 0" }}>
                  <span className="muted" style={{ fontSize: 12.5 }}>
                    {t(`licence.${field.labelKey}`)}
                  </span>
                  <div style={{ fontSize: 13.5, whiteSpace: "pre-wrap" }}>{value}</div>
                </div>
              );
            })}
          </div>

          {/* Only to the creator, and only once an option really was stated:
              telling somebody to price a licence they cannot read would be
              worse than saying nothing. */}
          {voice === "creator" && (
            <p className="muted" style={{ fontSize: 13, margin: "10px 0 0" }}>{t("licence.creatorPrice")}</p>
          )}
        </>
      )}
    </>
  );

  if (framed) {
    return (
      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>{t("licence.title")}</h3>
        <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{sub}</p>
        {body}
      </div>
    );
  }

  /* A section rather than a card, separated by the same rule the negotiation
     panel on the invitations page uses: a line above it, because what is above
     is the brand's brief and this is still part of it. */
  return (
    <div style={{ borderTop: "1px solid var(--line)", marginTop: 16, paddingTop: 14 }}>
      <span className="label" style={{ margin: 0 }}>{t("licence.title")}</span>
      <p className="muted" style={{ fontSize: 13, margin: "2px 0 0" }}>{sub}</p>
      {body}
    </div>
  );
}
