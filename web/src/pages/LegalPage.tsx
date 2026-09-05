import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";

/* THE PRIVACY POLICY. One component, one route, one content set —
   /legal/privacy in App.tsx.

   IT IS STILL PARAMETERISED ON `doc` RATHER THAN HARD-WIRED TO THE ONE
   DOCUMENT, because the Terms of Service is the next one and it is already
   drafted: it is held back only because which entity contracts with users,
   and under which law, is an open founder decision, and that answer changes
   nothing in the privacy policy. When it arrives the Terms are a second
   LegalDocument and a second route, not a second component.

   NOT MarketingPage, WHICH IS THE OBVIOUS THING TO REACH FOR. That component
   takes one titleKey and one bodyKey and renders a heading and a paragraph,
   which is the right shape for /for-brands and the wrong shape for a document
   with eleven sections: a legal text read as one paragraph is a legal text
   nobody reads, and an app-store reviewer looking for the deletion sentence
   needs a heading to find it under.

   NO AUTH WRAPPER, AND THAT IS THE WHOLE POINT OF THE PAGE. The route is not
   wrapped in BrandOnly, CreatorOnly or anything else, and Layout renders its
   MarketingNav for a signed-out visitor exactly as it does on /for-brands. A
   privacy policy that requires an account is not a published privacy policy —
   the people who most need to read it are the ones deciding whether to make
   an account, and an app-store reviewer types the URL cold, with no session
   at all.

   THE OUTLINE LIVES HERE AND THE WORDS LIVE IN lib/legalStrings.ts. That
   split is not decoration. main.tsx imports "./App" on its first line, so
   anything App.tsx reaches evaluates before the *Strings imports below it —
   and legalStrings adds footer.privacy into the footer.* group
   marketingStrings.ts owns, which only merges correctly if it is registered
   after it. App.tsx imports this file for the document; this file imports
   nothing from legalStrings, so that ordering holds. */

/* THE SAME DATE IN BOTH LANGUAGES — English privacy and French privacy —
   because it is one constant interpolated into one key rendered by one
   component. Two hand-written dates is two chances to publish a policy that
   says it took effect on a different day in French than in English, which is
   the kind of discrepancy a regulator reads as carelessness about the rest of
   it.

   ISO, not a localised date, deliberately: 03/04/2026 is March in one of the
   two languages this product ships in and April in the other. */
export const LEGAL_EFFECTIVE_DATE = "2026-09-05";

/* A block of a legal document. `key` is relative to the document's `ns`, so
   the privacy policy's "Security" heading is { kind: "heading", key:
   "securityTitle" } and resolves to legal.privacy.securityTitle — which is
   also how it is spelled in lib/legalStrings.ts, so a key is still greppable
   from either end.

   `list` rather than a run of paragraphs because the list in this document is
   genuinely an enumeration — who else sees your data — and a reader scanning
   for "does my payment provider get my number" finds a bullet faster than a
   sentence. */
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

/* THERE IS NO TERMS_DOCUMENT IN THIS FILE, AND THAT IS THE POINT OF THE
   SPLIT. The Terms of Service is drafted — outline and copy both — and it is
   blocked on one open founder decision: which entity contracts with the user
   (Mocktar Technologies in Benin, or Mocktar Technologies LLC in North
   Carolina) and under whose law. The clause is omitted rather than filled
   with a placeholder because the two failures are not symmetrical: a Terms
   page without it is incomplete, while a Terms page naming the wrong forum is
   a representation made to every user who accepted it.

   Nothing in the privacy policy turns on that answer, and the things waiting
   on a published privacy policy — Meta App Review's "Privacy policy URL" and
   "User data deletion" fields among them — are not waiting on the Terms. So
   the policy ships and the Terms follow: they stay on the branch of the pull
   request that drafted both, and that branch is rebased onto this one to
   carry the Terms alone. */

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

/* 68ch rather than the 720px MarketingPage uses. This is the longest text in
   the product and the measure is what makes it readable; a character-based
   one holds that line length in both languages, where French runs perceptibly
   longer than the English it was translated from. */
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
