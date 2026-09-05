import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";

/* THE PRIVACY POLICY AND THE TERMS OF SERVICE. One component, two routes,
   two content sets — /legal/privacy and /legal/terms in App.tsx.

   PARAMETERISING ON `doc` IS WHY THE SECOND DOCUMENT COST NOTHING. When the
   privacy policy shipped alone this component already took a LegalDocument
   rather than hard-wiring the one it had, on the stated bet that the Terms
   were coming. They are a second exported constant and a second route below;
   not one line of the rendering changed.

   NOT MarketingPage, WHICH IS THE OBVIOUS THING TO REACH FOR. That component
   takes one titleKey and one bodyKey and renders a heading and a paragraph,
   which is the right shape for /for-brands and the wrong shape for documents
   of eleven and fifteen sections: a legal text read as one paragraph is a legal text
   nobody reads, and an app-store reviewer looking for the deletion sentence
   needs a heading to find it under.

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
   French privacy, French terms — because it is one constant interpolated into
   one key rendered by one component. Four hand-written dates is four chances
   to publish a policy that says it took effect on a different day in French
   than in English, which is the kind of discrepancy a regulator reads as
   carelessness about the rest of it.

   ISO, not a localised date, deliberately: 03/04/2026 is March in one of the
   two languages this product ships in and April in the other. */
export const LEGAL_EFFECTIVE_DATE = "2026-09-05";

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
  | { kind: "list"; keys: readonly string[] };

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
    { kind: "para", key: "contactRegistration" }
  ]
};

/* THE TERMS OF SERVICE, AND THE ONE SECTION THAT IS NOT IN THIS OUTLINE.

   THERE IS NO GOVERNING-LAW SECTION BELOW, and its absence is the one thing
   to read before approving this page. Which entity contracts with the user —
   Mocktar Technologies in Benin, or Mocktar Technologies LLC in North
   Carolina — and under whose law, is an open founder decision. It is omitted
   rather than filled with a placeholder because the two failures are not
   symmetrical: a Terms page without the clause is incomplete, while a Terms
   page naming the wrong forum is a representation made to every user who
   accepted it.

   THE SECTION GOES BETWEEN `changes` AND `contactTitle`, which is where a
   reader looks for it and where the drafted document left the gap. Adding it
   is three things and no more: a `governingTitle` heading and a `governing`
   paragraph in this array, and the matching pair of strings in BOTH languages
   in lib/legalStrings.ts. Nothing else about this page changes.

   UNTIL THEN THIS ROUTE MUST NOT BE MERGED. The privacy policy shipped
   without it because nothing in a data-protection disclosure turns on which
   court hears a contract dispute. This document is the contract. */
export const TERMS_DOCUMENT: LegalDocument = {
  ns: "legal.terms",
  blocks: [
    { kind: "para", key: "intro" },
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
    /* SEVEN RULES, AND FOUR OF THEM WERE REWRITTEN BEFORE THIS SHIPPED.
       moneyHold gained the non-delivery refund, moneyCommission now names the
       amount RELEASED rather than the amount paid (a disputed split charges
       the fee on the released part only), and moneyRefund speaks of refunded
       money rather than "the full amount" so it covers a split too. The long
       note is above the French terms block in lib/legalStrings.ts. */
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
    { kind: "heading", key: "contactTitle" },
    { kind: "para", key: "contactAddress" },
    { kind: "para", key: "contactRegistration" }
  ]
};

/* Bold runs, written as **like this** in the copy so that the strings in
   lib/legalStrings.ts read the way the drafted document reads and a lawyer
   comparing the two is comparing sentences rather than markup.

   The whole of the emphasis support, and it stays that small on purpose:
   splitting on the marker means an odd number of markers can only ever
   emphasise the tail of a sentence, never leak a literal ** onto the page or
   swallow text. Nothing else about markdown is understood here, and nothing
   else should be — the moment this parses links, a legal document's rendering
   depends on a parser. */
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
