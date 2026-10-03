import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";

/* THE PRIVACY POLICY AND THE TERMS OF SERVICE. One component, two routes,
   two content sets — /legal/privacy and /legal/terms in App.tsx.

   PARAMETERISING ON `doc` IS WHY THE SECOND DOCUMENT COST NOTHING. When the
   privacy policy shipped alone this component already took a LegalDocument
   rather than hard-wiring the one it had, on the stated bet that the Terms
   were coming. They are a second exported constant and a second route below,
   and not one line of the rendering changed.

   NOT MarketingPage, WHICH IS THE OBVIOUS THING TO REACH FOR. That component
   takes one titleKey and one bodyKey and renders a heading and a paragraph,
   which is the right shape for /for-brands and the wrong shape for documents
   of eleven and sixteen sections: a legal text read as one paragraph is a
   legal text nobody reads, and an app-store reviewer looking for the
   deletion sentence needs a heading to find it under.

   NO AUTH WRAPPER, AND THAT IS THE WHOLE POINT OF THE PAGE. Neither route is
   wrapped in BrandOnly, CreatorOnly or anything else, and Layout renders its
   MarketingNav for a signed-out visitor exactly as it does on /for-brands. A
   privacy policy that requires an account is not a published privacy policy —
   the people who most need to read it are the ones deciding whether to make
   an account, and an app-store reviewer types the URL cold, with no session
   at all.

   THE OUTLINE LIVES HERE AND THE WORDS LIVE IN lib/legalStrings.ts. That
   split is not decoration. main.tsx imports "./App" on its first line, so
   anything App.tsx reaches evaluates before the *Strings imports below it —
   and legalStrings adds footer.privacy and footer.terms into the footer.*
   group marketingStrings.ts owns, which only merges correctly if it is
   registered after it. App.tsx imports this file for the two documents; this
   file imports nothing from legalStrings, so that ordering holds. */

/* THE SAME DATE ON ALL FOUR DOCUMENTS — English privacy, English terms,
   French privacy, French terms — because it is one constant interpolated
   into one key rendered by one component. Four hand-written dates is four
   chances to publish a document that says it took effect on a different day
   in French than in English, which is the kind of discrepancy a regulator
   reads as carelessness about the rest of it.

   IT MOVES WHEN EITHER DOCUMENT IS AMENDED, AND BOTH JUST WERE. The Terms
   are published for the first time and the privacy policy's verification
   paragraphs were narrowed in the same commit, so the one shared date
   advances for both rather than the privacy policy keeping an earlier one it
   no longer matches.

   ISO, not a localised date, deliberately: 03/04/2026 is March in one of the
   two languages this product ships in and April in the other. */
export const LEGAL_EFFECTIVE_DATE = "2026-10-03";

/* A block of a legal document. `key` is relative to the document's `ns`, so
   the privacy policy's "Security" heading is { kind: "heading", key:
   "securityTitle" } and resolves to legal.privacy.securityTitle — which is
   also how it is spelled in lib/legalStrings.ts, so a key is still greppable
   from either end.

   `list` rather than a run of paragraphs because both lists in these
   documents are genuinely enumerations — who else sees your data, and the
   seven rules of the escrow — and a reader scanning for "does Kolabo take a
   commission on a refund" finds a bullet faster than a sentence. */
export type LegalBlock =
  | { kind: "heading"; key: string }
  | { kind: "para"; key: string }
  | { kind: "list"; keys: readonly string[] }
  /* A link — and THE href LIVES HERE, IN CODE, NOT IN THE COPY. A URL inside
     a translated string is a URL a translator can mangle, and it would have to
     be written identically in both bundles anyway: exactly the argument
     lib/legalStrings.ts already makes for keeping the registration identifiers
     and the postal address out of translation. `key` resolves to the VISIBLE
     TEXT, which is the address without its scheme; `href` carries the full
     https:// one. A wrong URL is therefore a one-line diff in this file rather
     than something hiding in the middle of a paragraph in two languages. */
  | { kind: "link"; key: string; href: string };

export type LegalDocument = {
  /* The i18n group this document's copy lives under. */
  ns: string;
  blocks: readonly LegalBlock[];
};

/* The order below is the order of the drafted document, and it is not
   arbitrary: what we collect comes before why, why before who else sees it,
   and the things a reader is most likely to be looking for — deletion,
   children, contact — are last because that is where a reader looks for
   them. */
export const PRIVACY_DOCUMENT: LegalDocument = {
  ns: "legal.privacy",
  blocks: [
    { kind: "para", key: "intro" },
    { kind: "heading", key: "whoTitle" },
    { kind: "para", key: "who" },
    /* THE ENTITY REGISTER, AND IT IS A LINK NOW RATHER THAN PRINTED TEXT.
       Both places this document points at mocktar.com used to render the bare
       address, so a Meta or App Store reviewer checking who they are dealing
       with had to select it and paste it — and the sentence-ending full stop
       sat directly against it, which is a copy-paste error waiting to happen.

       NO TRAILING SLASH. The copy used to print /legal/entities/. Both forms
       were fetched and both resolve, so dropping it repairs nothing that is
       broken today; it is the canonical form rather than one that depends on
       the host continuing to forgive a slash. See lib/legalStrings.ts. */
    { kind: "link", key: "whoLink", href: "https://mocktar.com/legal/entities" },
    { kind: "heading", key: "collectTitle" },
    { kind: "para", key: "collectAccount" },
    { kind: "para", key: "collectVerify" },
    { kind: "para", key: "collectPublish" },
    { kind: "para", key: "collectSocial" },
    { kind: "para", key: "collectDocs" },
    { kind: "para", key: "collectMoney" },
    { kind: "para", key: "collectWork" },
    { kind: "para", key: "collectTech" },
    { kind: "heading", key: "whyTitle" },
    { kind: "para", key: "why" },
    { kind: "para", key: "whyNoSale" },
    { kind: "heading", key: "sharedTitle" },
    /* SIX RECIPIENTS AND NOT SEVEN. "sharedSms" used to sit between
       sharedGateway and sharedSocial, and it named an SMS provider that does
       not exist: backend/app/modules/auth/otp.py ships LoggingSender and
       nothing else. It was removed here and in both languages rather than
       softened, because a list headed "who else sees it" is read as a list of
       who actually does. Whoever integrates a provider puts the entry back in
       this array and the two strings back in lib/legalStrings.ts — the long
       note there says exactly what to restore. */
    {
      kind: "list",
      keys: [
        "sharedGateway",
        "sharedSocial",
        "sharedAi",
        "sharedHosting",
        "sharedCounterparty",
        "sharedAuthorities"
      ]
    },
    { kind: "heading", key: "whereTitle" },
    { kind: "para", key: "where" },
    { kind: "heading", key: "retentionTitle" },
    { kind: "para", key: "retention" },
    { kind: "heading", key: "rightsTitle" },
    { kind: "para", key: "rightsEdit" },
    { kind: "para", key: "rightsLimits" },
    { kind: "heading", key: "securityTitle" },
    { kind: "para", key: "security" },
    { kind: "heading", key: "childrenTitle" },
    { kind: "para", key: "children" },
    { kind: "heading", key: "changesTitle" },
    { kind: "para", key: "changes" },
    { kind: "heading", key: "contactTitle" },
    { kind: "para", key: "contactAddress" },
    { kind: "para", key: "contactRegistration" },
    /* The same address as whoLink above, and deliberately repeated: a reader
       who opened the policy at "Contact" must not have to scroll back to the
       top to find where the registration details are published. One href,
       written twice here, rather than one string carrying a URL. */
    { kind: "link", key: "contactRegistrationLink", href: "https://mocktar.com/legal/entities" }
  ]
};

/* THE TERMS OF SERVICE, AND THE SECTION THAT USED TO BE MISSING FROM IT.

   THE GOVERNING-LAW SECTION IS NOW IN THIS OUTLINE. Where the previous
   version of this comment said there was no TERMS_DOCUMENT because the
   clause was an open founder decision, the decision has been made: Benin law
   and the courts of Cotonou, as governingTitle and governing, between
   `changes` and `contactTitle` — which is both where a reader looks for it
   and where the drafted document left the gap.

   THAT DOES NOT MAKE THIS PAGE APPROVED. The clause rests on counsel's
   reading of two things that nothing in this repo settles: that party
   autonomy gives a chosen law and forum effect across the five launch
   markets, and that creators contract here as sellers rather than as
   consumers, so the protective consumer-forum rules do not pull a dispute
   back to a creator's own country. lib/legalStrings.ts carries that note in
   full. The Terms go back to counsel before they are relied on.

   THE SECOND ENTITY IS DISCLOSED RATHER THAN LEFT TO A FOOTER. `intro`
   identifies Mocktar Technologies in Benin by register number and seat, and
   the `group` paragraph plus the `groupLink` block name Mocktar Technologies
   LLC in North Carolina and point at the entity register. The same register
   is linked again from the contact section, exactly as the privacy policy
   links it twice and for the same reason: a reader who opened the document at
   "Contact" should not have to scroll back to the top.

   BOTH DOCUMENTS NOW POINT AT mocktar.com/legal/entities, so that page has to
   carry the relationship between the two companies. It is the one claim on
   this page whose truth lives outside this repo. */
export const TERMS_DOCUMENT: LegalDocument = {
  ns: "legal.terms",
  blocks: [
    { kind: "para", key: "intro" },
    /* THE GROUP DISCLOSURE SITS WITH THE PARTY IT QUALIFIES, immediately
       after the sentence that names the contracting company, rather than down
       in the contact section. A reader learning which of two companies they
       are dealing with should learn it where they are told who they are
       dealing with. */
    { kind: "para", key: "group" },
    { kind: "link", key: "groupLink", href: "https://mocktar.com/legal/entities" },
    { kind: "heading", key: "whatTitle" },
    { kind: "para", key: "what" },
    { kind: "heading", key: "whoTitle" },
    { kind: "para", key: "who" },
    { kind: "heading", key: "accountTitle" },
    { kind: "para", key: "account" },
    { kind: "heading", key: "creatorsTitle" },
    { kind: "para", key: "creators" },
    { kind: "heading", key: "businessesTitle" },
    { kind: "para", key: "businesses" },
    { kind: "heading", key: "moneyTitle" },
    /* SEVEN RULES. Four of them were rewritten in #164 against the code —
       moneyHold gained the non-delivery refund, and moneyCommission names the
       amount RELEASED rather than the amount paid, because a disputed split
       charges the fee on the released part only. Those four are carried here
       as #164 left them and were NOT re-read against current main; the header
       of lib/legalStrings.ts says so in as many words. */
    {
      kind: "list",
      keys: [
        "moneyFund",
        "moneyHold",
        "moneyRelease",
        "moneyCommission",
        "moneyRefund",
        "moneyPayout",
        "moneyCurrency"
      ]
    },
    { kind: "heading", key: "offPlatformTitle" },
    { kind: "para", key: "offPlatform" },
    { kind: "heading", key: "disputesTitle" },
    { kind: "para", key: "disputes" },
    { kind: "heading", key: "ownershipTitle" },
    { kind: "para", key: "ownership" },
    { kind: "heading", key: "prohibitedTitle" },
    { kind: "para", key: "prohibited" },
    { kind: "heading", key: "availabilityTitle" },
    { kind: "para", key: "availability" },
    { kind: "heading", key: "liabilityTitle" },
    { kind: "para", key: "liability" },
    { kind: "heading", key: "endingTitle" },
    { kind: "para", key: "ending" },
    { kind: "heading", key: "changesTitle" },
    { kind: "para", key: "changes" },
    { kind: "heading", key: "governingTitle" },
    { kind: "para", key: "governing" },
    { kind: "heading", key: "contactTitle" },
    { kind: "para", key: "contactAddress" },
    { kind: "para", key: "contactRegistration" },
    { kind: "link", key: "contactRegistrationLink", href: "https://mocktar.com/legal/entities" }
  ]
};

/* Bold runs, written as **like this** in the copy so that the strings in
   lib/legalStrings.ts read the way the drafted document reads and a lawyer
   comparing the two is comparing sentences rather than markup.

   The whole of the emphasis support, and it stays that small on purpose:
   splitting on the marker means an odd number of markers can only ever
   emphasise the tail of a sentence, never leak a literal ** onto the page or
   swallow text.

   THIS IS STILL THE ONLY THING PARSED, AND THE PAGE NOW HAS LINKS ON IT. That
   is not a contradiction. This comment used to end "the moment this parses
   links, a legal document's rendering depends on a parser", and that objection
   stands word for word — which is precisely why the links are NOT parsed out
   of the copy. The renderer understands four DECLARED block kinds — heading,
   para, list and link — and a link is an entry in the outline carrying its own
   href, not syntax discovered inside a translated sentence. The copy still
   contains no markup at all beyond the bold marker, so there is still nothing
   a parser could misread, mis-nest or silently drop. Anything else this page
   ever needs to render should arrive the same way: as a block kind, not as a
   character sequence somebody has to remember to escape. */
function Emphasised({ text }: { text: string }) {
  return (
    <>
      {text.split("**").map((run, i) =>
        i % 2 === 1 ? <strong key={i}>{run}</strong> : <Fragment key={i}>{run}</Fragment>
      )}
    </>
  );
}

/* 68ch rather than the 720px MarketingPage uses. These are the two longest
   texts in the product and the measure is what makes them readable; a
   character-based one holds that line length in both languages, where French
   runs perceptibly longer than the English it was translated from. */
const COLUMN: React.CSSProperties = { maxWidth: "68ch" };
const HEADING: React.CSSProperties = { fontSize: 20, marginTop: 32 };
const PARA: React.CSSProperties = { marginTop: 0, marginBottom: 14 };

export default function LegalPage({ doc }: { doc: LegalDocument }) {
  const { t } = useTranslation();
  return (
    <Layout>
      <div className="container page" style={COLUMN}>
        <h1>{t(`${doc.ns}.title`)}</h1>
        <p className="muted" style={{ marginTop: -4 }}>
          {t("legal.effective", { date: LEGAL_EFFECTIVE_DATE })}
        </p>
        {doc.blocks.map((block) => {
          if (block.kind === "heading") {
            return (
              <h2 key={block.key} style={HEADING}>
                {t(`${doc.ns}.${block.key}`)}
              </h2>
            );
          }
          if (block.kind === "link") {
            /* Wrapped in a paragraph so it keeps the document's vertical
               rhythm rather than running into the sentence above it, and
               target/rel because this is the one thing on the page that
               leaves the product. */
            return (
              <p key={block.key} style={PARA}>
                <a href={block.href} target="_blank" rel="noreferrer">
                  {t(`${doc.ns}.${block.key}`)}
                </a>
              </p>
            );
          }
          if (block.kind === "list") {
            return (
              <ul key={block.keys[0]} style={{ paddingLeft: 22, marginTop: 0 }}>
                {block.keys.map((key) => (
                  <li key={key} style={{ marginBottom: 10 }}>
                    <Emphasised text={t(`${doc.ns}.${key}`)} />
                  </li>
                ))}
              </ul>
            );
          }
          return (
            <p key={block.key} style={PARA}>
              <Emphasised text={t(`${doc.ns}.${block.key}`)} />
            </p>
          );
        })}
      </div>
    </Layout>
  );
}
