import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { licenceSentences, optionOf, redistributes, type LicenceTerms } from "../../lib/licenceTerms";
import { Hint } from "../ui";
import { colors, family, font, radius, space } from "../../theme";
/* Side-effect import: registers the licence.* copy on the i18n instance.
   Without it this block renders "licence.noticeTitle" at the reader. Same
   arrangement the party, package and payment sections use; see
   lib/licenceStrings.ts for why the keys live outside strings.ts. */
import "../../lib/licenceStrings";

/* What the brand may do with the content, as the creator reads it BEFORE
   accepting.

   THIS BLOCK IS THE POINT OF THE WHOLE CHANGE. A creator prices option 2
   differently from option 1, because a video that runs as a paid advert for a
   year is worth more than a post that lives on their own feed and stops
   there. Under the old flow the licence first appeared in the contract body,
   which is generated AFTER acceptance, so a creator accepting a brief or a
   direct order was accepting terms they had never read and could not have
   priced. Everything else in this feature exists to put this paragraph on
   screen next to the button that accepts.

   SO IT IS NOT COLLAPSIBLE, not behind a chevron, and not at the bottom of
   the card. It sits in the reading order where the decision is made: after
   what is being asked for, before the price is typed.

   IT RENDERS SOMETHING IN EVERY STATE, including the empty one. An absent
   option and option 1 look the same if silence means both, and they are not
   the same thing: option 1 is a term a creator can price, while nothing
   stated is a contract that cannot be generated at all (the backend answers
   contract_licence_terms_missing, which lib/errorMessages.ts translates). So
   a brief with no licence terms says so in words and names the next step,
   which is to ask the brand, because the brand is the only party who can
   answer.

   READ ONLY, deliberately, and it takes a whole LicenceTerms rather than
   loose fields so a caller cannot pass four of the five. Nothing here edits
   anything: the licence is the brand's statement, the creator's reply to it
   is a price or a refusal, and both of those already have controls on the
   same card.

   IT LIVES UNDER components/campaigns BECAUSE A DIRECT ORDER IS A CAMPAIGN.
   The same five columns hang off a brief and off an order, its brand side
   twin LicenceFields.tsx writes them, and keeping the pair of files together
   is what makes a change to one an obvious diff next to the other, even
   though this half is read by two creator screens. */
export function LicenceTermsNotice({ terms }: { terms: LicenceTerms | null | undefined }) {
  const { t } = useTranslation();
  const option = optionOf(terms);
  const lines = licenceSentences(terms, t);

  return (
    <View style={styles.block}>
      <Text style={styles.title}>{t("licence.noticeTitle")}</Text>
      {option === null ? (
        <Text style={styles.body}>{t("licence.notStated")}</Text>
      ) : (
        <View style={{ gap: space(1.5) }}>
          {/* Index keys: these are sentences built fresh on every render from
              one row, not a list anybody reorders or removes from. */}
          {lines.map((line, i) => (
            <Text key={i} style={styles.body}>
              {line}
            </Text>
          ))}
        </View>
      )}
      {/* Only when the brand is claiming something beyond the creator's own
          accounts. Under option 1 there is no extra use to price and this
          line would be noise on a card that is already long. */}
      {redistributes(option) ? <Hint>{t("licence.beforeAccept")}</Hint> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  /* Set off from the card's body copy rather than blended into it: an indigo
     edge and a tinted field, so the paragraph reads as terms somebody is
     being asked to agree to and not as more of the brief's description. The
     same indigo the app uses for a primary action, because this is the thing
     on the card that has to be read before one is taken. */
  block: {
    marginTop: space(3),
    borderWidth: 1,
    borderColor: colors.line,
    borderLeftWidth: 3,
    borderLeftColor: colors.indigo,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
    padding: space(3),
  },
  title: {
    fontSize: font.small,
    fontFamily: family.bodyBold,
    color: colors.ink,
    marginBottom: space(2),
  },
  /* ink, not muted. Muted is for hints a reader may skip, and a creator who
     skips this one accepts terms they did not price. */
  body: { fontSize: font.small, fontFamily: family.body, color: colors.ink, lineHeight: 20 },
});
