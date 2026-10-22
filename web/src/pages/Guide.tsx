import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";

/* THE USER GUIDE. One page, two roles and a question list, with the words in
   lib/guideStrings.ts: the same split LegalPage.tsx makes, for the same
   reason, which is that an outline is code and a sentence is copy.

   WHY A PAGE AND NOT AN FAQ SECTION. There is already a four question
   accordion at the bottom of the landing page, reached from the footer as
   /#faq, and it is the right size for a visitor deciding whether to sign up.
   It is the wrong shape for somebody who has signed up and is stuck: a person
   whose payout has not arrived needs the paragraph about the payout method,
   and they need to be able to be SENT to it. That is what an anchored section
   in a numbered document gives and a closed accordion on a marketing page
   does not.

   NO AUTH WRAPPER, like the legal pages and for the same reason. Half of this
   document is read by somebody who has not finished creating an account, and
   an app store reviewer opens it cold with no session at all.

   THE NUMBERS ARE COMPUTED, never written in the copy. A section is numbered
   by its position in SECTIONS and a topic by its position inside one, so
   inserting a topic renumbers the contents list and the body together. Hand
   written numbers drift the first time somebody reorders two paragraphs, and
   a guide whose numbering is wrong is a guide nobody trusts the rest of.

   THE ANCHOR IDS ARE LANGUAGE NEUTRAL, which is a decision rather than
   laziness. There is one /guide route carrying both languages through the
   switch, not a route per language, so the id cannot be the heading's words:
   it would read as French to half the audience and as English to the other
   half, and it would change under a reader who switched language with a link
   already copied. "creator-payout" is nobody's prose and survives both. */

type GuideBlock =
  | { kind: "para"; key: string }
  /* An ordered list, for the only thing that is genuinely a sequence: do this,
     then this. Everything else is a list or a paragraph, because numbering
     things that are not steps teaches a reader that the numbers mean nothing. */
  | { kind: "steps"; keys: readonly string[] }
  | { kind: "list"; keys: readonly string[] }
  /* The one thing on the page that is set apart. Reserved for the sentence a
     reader will wish they had seen first: the payout method that has to exist
     before money can move, the escrow that has to be funded before work
     starts, the difference between requesting changes and opening a dispute. */
  | { kind: "note"; key: string }
  /* The address, as a mailto. The href lives here and not in the copy, for the
     reason LegalPage.tsx gives about its links: an address inside a translated
     string is an address a translator can mangle, and it would have to be
     written identically in both bundles anyway. */
  | { kind: "mail"; key: string };

type GuideTopic = {
  /* Appended to the page URL, so it is part of this file's public surface.
     Renaming one breaks a link somebody has already pasted into an email. */
  id: string;
  titleKey: string;
  blocks: readonly GuideBlock[];
};

type GuideSection = {
  id: string;
  /* The i18n group this section's copy lives under, so a key is greppable from
     either end: guide.creator + accountTitle is spelled guide.creator.
     accountTitle in lib/guideStrings.ts. */
  ns: string;
  introKey?: string;
  topics: readonly GuideTopic[];
};

/* The order is the order somebody lives it. Creators first because a
   marketplace with no creators has nothing to sell, and because the creator
   path is the one with the step that cannot be skipped late: the payout method
   has to exist before the money can leave. */
const SECTIONS: readonly GuideSection[] = [
  {
    id: "creator",
    ns: "guide.creator",
    introKey: "intro",
    topics: [
      {
        id: "creator-account",
        titleKey: "accountTitle",
        blocks: [
          { kind: "steps", keys: ["account1", "account2", "account3"] },
          { kind: "para", key: "accountGoogle" },
          { kind: "note", key: "accountNote" }
        ]
      },
      {
        id: "creator-profile",
        titleKey: "profileTitle",
        blocks: [
          { kind: "para", key: "profileIntro" },
          { kind: "steps", keys: ["profile1", "profile2", "profile3", "profile4", "profile5"] },
          { kind: "note", key: "profileNote" }
        ]
      },
      {
        id: "creator-social",
        titleKey: "socialTitle",
        blocks: [
          { kind: "para", key: "social1" },
          { kind: "para", key: "social2" },
          { kind: "note", key: "socialNote" }
        ]
      },
      {
        id: "creator-packages",
        titleKey: "packagesTitle",
        blocks: [
          { kind: "para", key: "packages1" },
          { kind: "para", key: "packages2" }
        ]
      },
      {
        id: "creator-work",
        titleKey: "workTitle",
        blocks: [
          { kind: "para", key: "workIntro" },
          { kind: "list", keys: ["work1", "work2", "work3"] },
          { kind: "para", key: "workNegotiate" }
        ]
      },
      {
        id: "creator-contract",
        titleKey: "contractTitle",
        blocks: [
          { kind: "para", key: "contract1" },
          { kind: "para", key: "contract2" },
          { kind: "note", key: "contractNote" }
        ]
      },
      {
        id: "creator-deliver",
        titleKey: "deliverTitle",
        blocks: [
          { kind: "steps", keys: ["deliver1", "deliver2", "deliver3"] },
          { kind: "para", key: "deliverWindow" },
          { kind: "para", key: "deliverWithdraw" },
          { kind: "para", key: "deliverChanges" }
        ]
      },
      {
        id: "creator-payout",
        titleKey: "paidTitle",
        blocks: [
          { kind: "para", key: "paid1" },
          { kind: "para", key: "paid2" },
          { kind: "note", key: "paidNote" },
          { kind: "para", key: "paid3" }
        ]
      },
      {
        id: "creator-dispute",
        titleKey: "disputeTitle",
        blocks: [
          { kind: "para", key: "dispute1" },
          { kind: "para", key: "dispute2" },
          { kind: "note", key: "disputeNote" }
        ]
      }
    ]
  },
  {
    id: "brand",
    ns: "guide.brand",
    introKey: "intro",
    topics: [
      {
        id: "brand-account",
        titleKey: "accountTitle",
        blocks: [
          { kind: "steps", keys: ["account1", "account2", "account3"] },
          { kind: "note", key: "accountNote" }
        ]
      },
      {
        id: "brand-find",
        titleKey: "findTitle",
        blocks: [
          { kind: "para", key: "find1" },
          { kind: "para", key: "find2" },
          { kind: "para", key: "find3" }
        ]
      },
      {
        id: "brand-order",
        titleKey: "orderTitle",
        blocks: [
          { kind: "steps", keys: ["order1", "order2", "order3"] },
          { kind: "para", key: "orderRule" },
          { kind: "note", key: "orderNote" }
        ]
      },
      {
        id: "brand-brief",
        titleKey: "briefTitle",
        blocks: [
          { kind: "para", key: "brief1" },
          { kind: "para", key: "brief2" },
          { kind: "para", key: "brief3" }
        ]
      },
      {
        id: "brand-contract",
        titleKey: "signTitle",
        blocks: [{ kind: "para", key: "sign1" }]
      },
      {
        id: "brand-pay",
        titleKey: "payTitle",
        blocks: [
          { kind: "para", key: "payIntro" },
          { kind: "steps", keys: ["pay1", "pay2", "pay3", "pay4"] },
          { kind: "para", key: "payAfter" },
          { kind: "note", key: "payNote" }
        ]
      },
      {
        id: "brand-review",
        titleKey: "reviewTitle",
        blocks: [
          { kind: "para", key: "reviewIntro" },
          { kind: "list", keys: ["review1", "review2"] },
          { kind: "para", key: "reviewWindow" },
          { kind: "note", key: "reviewNote" }
        ]
      },
      {
        id: "brand-spend",
        titleKey: "spendTitle",
        blocks: [
          { kind: "para", key: "spend1" },
          { kind: "para", key: "spend2" }
        ]
      },
      {
        id: "brand-dispute",
        titleKey: "disputeTitle",
        blocks: [
          { kind: "para", key: "dispute1" },
          { kind: "para", key: "dispute2" }
        ]
      }
    ]
  },
  {
    id: "questions",
    ns: "guide.faq",
    topics: [
      {
        id: "password",
        titleKey: "passwordTitle",
        blocks: [{ kind: "steps", keys: ["password1", "password2", "password3"] }]
      },
      {
        id: "account-menu",
        titleKey: "menuTitle",
        blocks: [
          { kind: "para", key: "menu1" },
          { kind: "para", key: "menu2" }
        ]
      },
      {
        id: "commission",
        titleKey: "commissionTitle",
        blocks: [
          { kind: "para", key: "commission1" },
          { kind: "para", key: "commission2" }
        ]
      },
      {
        id: "countries",
        titleKey: "countriesTitle",
        blocks: [
          { kind: "para", key: "countries1" },
          { kind: "para", key: "countries2" }
        ]
      },
      {
        id: "payout-timing",
        titleKey: "timelineTitle",
        blocks: [
          { kind: "para", key: "timeline1" },
          { kind: "para", key: "timeline2" }
        ]
      },
      {
        id: "delete-account",
        titleKey: "deleteTitle",
        blocks: [
          { kind: "para", key: "delete1" },
          { kind: "para", key: "delete2" }
        ]
      },
      {
        id: "contact",
        titleKey: "contactTitle",
        blocks: [
          { kind: "para", key: "contact1" },
          { kind: "mail", key: "contactLink" }
        ]
      }
    ]
  }
];

/* 68ch, the measure the legal pages use, and for the reason stated there: it
   holds a readable line length in both languages, where the French runs
   perceptibly longer than the English it was translated from. */
const COLUMN: React.CSSProperties = { maxWidth: "68ch" };

/* Every heading clears the sticky 64px header when it is jumped to. This is
   scroll-margin rather than an offset computed in the scroll handler, so it
   is also correct when the browser does the jump itself on a cold load, which
   is the case a handler never sees. */
const SECTION_HEADING: React.CSSProperties = { fontSize: 23, marginTop: 44, scrollMarginTop: 84 };
const TOPIC_HEADING: React.CSSProperties = { fontSize: 17.5, marginTop: 30, scrollMarginTop: 84 };
const PARA: React.CSSProperties = { marginTop: 0, marginBottom: 14 };
const NOTE: React.CSSProperties = {
  margin: "0 0 14px", padding: "12px 16px", background: "var(--surface-2)",
  borderRadius: "var(--radius-sm)", fontSize: 14.5
};
const TOC: React.CSSProperties = {
  margin: "26px 0 0", padding: "18px 22px", background: "var(--surface)",
  border: "1px solid var(--line)", borderRadius: "var(--radius)"
};

export default function Guide() {
  const { t } = useTranslation();
  const { hash } = useLocation();

  /* react-router does not scroll to a hash on a client side navigation, which
     is the same gap the landing page's FAQ section handles for itself. Without
     this, a support reply saying "see /guide#creator-payout" would land the
     reader at the top of a long document, which is the one outcome an anchor
     exists to prevent.

     Keyed on the hash rather than running once on mount, so clicking an entry
     in the contents list works a second time after the reader has scrolled
     away from it. */
  useEffect(() => {
    if (!hash) return;
    document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [hash]);

  return (
    <Layout>
      <div className="container page" style={COLUMN}>
        <h1>{t("guide.title")}</h1>
        <p className="muted" style={{ marginTop: -4 }}>{t("guide.sub")}</p>
        <p style={PARA}>{t("guide.scope")}</p>

        <nav style={TOC} aria-label={t("guide.tocTitle")}>
          <strong style={{ fontFamily: "var(--font-display)", fontSize: 15 }}>
            {t("guide.tocTitle")}
          </strong>
          {SECTIONS.map((section, s) => (
            <div key={section.id} style={{ marginTop: 12 }}>
              <a href={`#${section.id}`} style={{ fontWeight: 600, fontSize: 14.5 }}>
                {s + 1}. {t(`${section.ns}.title`)}
              </a>
              <ul style={{ margin: "6px 0 0", paddingLeft: 20, listStyle: "none" }}>
                {section.topics.map((topic, i) => (
                  <li key={topic.id} style={{ marginBottom: 3 }}>
                    <a href={`#${topic.id}`} style={{ fontSize: 14, color: "var(--muted)" }}>
                      {s + 1}.{i + 1} {t(`${section.ns}.${topic.titleKey}`)}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {SECTIONS.map((section, s) => (
          <section key={section.id}>
            <h2 id={section.id} style={SECTION_HEADING}>
              {s + 1}. {t(`${section.ns}.title`)}
            </h2>
            {section.introKey && (
              <p className="muted" style={PARA}>{t(`${section.ns}.${section.introKey}`)}</p>
            )}
            {section.topics.map((topic, i) => (
              <div key={topic.id}>
                <h3 id={topic.id} style={TOPIC_HEADING}>
                  {s + 1}.{i + 1} {t(`${section.ns}.${topic.titleKey}`)}
                </h3>
                {topic.blocks.map((block) => {
                  if (block.kind === "steps") {
                    return (
                      <ol key={block.keys[0]} style={{ paddingLeft: 22, marginTop: 0 }}>
                        {block.keys.map((key) => (
                          <li key={key} style={{ marginBottom: 8 }}>
                            {t(`${section.ns}.${key}`)}
                          </li>
                        ))}
                      </ol>
                    );
                  }
                  if (block.kind === "list") {
                    return (
                      <ul key={block.keys[0]} style={{ paddingLeft: 22, marginTop: 0 }}>
                        {block.keys.map((key) => (
                          <li key={key} style={{ marginBottom: 8 }}>
                            {t(`${section.ns}.${key}`)}
                          </li>
                        ))}
                      </ul>
                    );
                  }
                  if (block.kind === "note") {
                    return (
                      <p key={block.key} style={NOTE}>{t(`${section.ns}.${block.key}`)}</p>
                    );
                  }
                  if (block.kind === "mail") {
                    const address = t(`${section.ns}.${block.key}`);
                    return (
                      <p key={block.key} style={PARA}>
                        <a href={`mailto:${address}`}>{address}</a>
                      </p>
                    );
                  }
                  return (
                    <p key={block.key} style={PARA}>{t(`${section.ns}.${block.key}`)}</p>
                  );
                })}
              </div>
            ))}
          </section>
        ))}
      </div>
    </Layout>
  );
}
