import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { COMMISSION_BPS, commissionFor } from "../lib/pricing";

/* THE THREE PAGES THE HEADER LINKS TO: /for-brands, /for-creators, /pricing.

   WHAT THIS REPLACES. One component took a titleKey and a bodyKey, rendered a
   heading and a paragraph, and then a card containing
   marketingPage.placeholder: "Cette page est en cours de rédaction." That was
   honest when the links needed somewhere to go, and it stopped being
   acceptable once the nav and the footer pointed at all three from every page
   of the site, because it is what a Meta reviewer or an app-store reviewer
   reads when they click "Pour les marques".

   SAME SHAPE AS THE OTHER LONG PAGES. An outline of declared block kinds
   here, the sentences in lib/sitePageStrings.ts, exactly as LegalPage.tsx and
   Guide.tsx are arranged. A third copy of that idea is a sign the renderer
   should be shared, and it should, later: the three differ enough today
   (emphasis, link blocks, numbering, a computed example) that merging them
   now would mean a renderer with three modes, which is worse than three small
   ones. Worth doing when a fourth appears.

   THE RATE IS INTERPOLATED, NEVER TYPED. Every sentence carrying the
   commission has a {{pct}} placeholder and gets COMMISSION_BPS / 100, so the
   number exists once in the source. lib/pricing.test.ts holds that constant
   to settings.commission_bps in the backend, which is what makes it safe to
   publish rather than merely convenient.

   THE WORKED EXAMPLE IS COMPUTED THROUGH commissionFor, the same integer
   division payments/service.py performs, with the rounding remainder left on
   the creator's side. So the example cannot drift from the rate printed above
   it, and it cannot drift from what the server would actually do with that
   amount either. Only the row labels are copy. */

type SiteBlock =
  | { kind: "heading"; key: string }
  | { kind: "para"; key: string }
  | { kind: "list"; keys: readonly string[] }
  /* Ordered, for the only thing on these pages that is genuinely a sequence:
     the "how it works" run. */
  | { kind: "steps"; keys: readonly string[] }
  /* The pricing page's worked transaction. The amount lives in the outline
     rather than the copy because it is arithmetic, not language: both
     translations describe the same transaction and neither should be able to
     state a different one. */
  | { kind: "example"; amount: number; currency: string };

export type SitePage = {
  /* The i18n group, so a key stays greppable from either end: forBrands plus
     whyTitle is spelled forBrands.whyTitle in lib/sitePageStrings.ts. */
  ns: string;
  blocks: readonly SiteBlock[];
};

/* Why, then how, then what it costs, then where it works. A brand arriving
   cold wants the reason before the mechanism, and the price before the
   footprint. */
export const BRANDS_PAGE: SitePage = {
  ns: "forBrands",
  blocks: [
    { kind: "heading", key: "whyTitle" },
    { kind: "list", keys: ["why1", "why2", "why3", "why4", "why5"] },
    { kind: "heading", key: "howTitle" },
    { kind: "steps", keys: ["how1", "how2", "how3", "how4"] },
    { kind: "heading", key: "feeTitle" },
    { kind: "para", key: "fee1" },
    { kind: "para", key: "fee2" },
    { kind: "heading", key: "whereTitle" },
    { kind: "para", key: "where1" },
    { kind: "para", key: "where2" }
  ]
};

/* The same order, with the footprint section replaced by how the money
   actually reaches them. For a creator that is the question, and burying it
   under a list of countries would be answering a different one. */
export const CREATORS_PAGE: SitePage = {
  ns: "forCreators",
  blocks: [
    { kind: "heading", key: "whyTitle" },
    { kind: "list", keys: ["why1", "why2", "why3", "why4", "why5"] },
    { kind: "heading", key: "howTitle" },
    { kind: "steps", keys: ["how1", "how2", "how3", "how4"] },
    { kind: "heading", key: "feeTitle" },
    { kind: "para", key: "fee1" },
    { kind: "para", key: "fee2" },
    { kind: "para", key: "fee3" },
    { kind: "heading", key: "payoutTitle" },
    { kind: "para", key: "payout1" },
    { kind: "para", key: "payout2" }
  ]
};

/* FREE FIRST, AND THAT IS THE ARGUMENT OF THE PAGE. Most of this product
   costs nothing: searching needs no account at all, and publishing a profile,
   publishing packages and negotiating a price are free for everybody. One
   commission, once, when a creator is paid. Leading with the fee would
   describe a subscription product this is not. */
export const PRICING_PAGE: SitePage = {
  ns: "pricingPage",
  blocks: [
    { kind: "heading", key: "freeTitle" },
    { kind: "list", keys: ["free1", "free2", "free3", "free4"] },
    { kind: "heading", key: "feeTitle" },
    { kind: "para", key: "fee1" },
    { kind: "para", key: "fee2" },
    { kind: "heading", key: "exampleTitle" },
    /* 25,000 XOF: the figure docs/PAYMENTS_FEDAPAY.md works through, and a
       realistic order in the launch markets. Kept identical to the document so
       the two describe one transaction, and pinned in lib/pricing.test.ts. */
    { kind: "example", amount: 25000, currency: "XOF" },
    { kind: "heading", key: "whenTitle" },
    { kind: "para", key: "when1" },
    { kind: "para", key: "when2" },
    { kind: "para", key: "when3" },
    { kind: "heading", key: "payTitle" },
    { kind: "para", key: "pay1" },
    { kind: "para", key: "pay2" }
  ]
};

const COLUMN: React.CSSProperties = { maxWidth: 720 };
const HEADING: React.CSSProperties = { fontSize: 20, marginTop: 32 };
const PARA: React.CSSProperties = { marginTop: 0, marginBottom: 14 };
const ROW: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", gap: 16,
  padding: "10px 0", borderBottom: "1px solid var(--line)"
};
const LAST_ROW: React.CSSProperties = { ...ROW, borderBottom: "none", fontWeight: 600 };

export default function MarketingPage({ page }: { page: SitePage }) {
  const { t, i18n } = useTranslation();
  /* Handed to every t() call on the page. i18next ignores an interpolation
     value a string does not use, so passing it once is simpler and safer than
     remembering which of twenty sentences carries the placeholder. */
  const vars = { pct: COMMISSION_BPS / 100 };

  /* Grouped digits, in the reader's language: 25 000 in French and 25,000 in
     English. The currency stays a bare code rather than a symbol, which is
     what the rest of the product does with XOF. */
  function money(amount: number, currency: string): string {
    return `${new Intl.NumberFormat(i18n.language).format(amount)} ${currency}`;
  }

  return (
    <Layout>
      <div className="container page" style={COLUMN}>
        <h1>{t(`${page.ns}.title`)}</h1>
        <p className="muted" style={{ marginTop: -4 }}>{t(`${page.ns}.sub`, vars)}</p>

        {page.blocks.map((block) => {
          if (block.kind === "heading") {
            return (
              <h2 key={block.key} style={HEADING}>{t(`${page.ns}.${block.key}`, vars)}</h2>
            );
          }
          /* THE BRANCH THIS RENDERER WAS MISSING. Without it the map fell from
             steps straight into the example below, which read block.amount off
             a union member that has no amount: a type error, and had it
             compiled, every paragraph on all three pages would have rendered
             as the worked table. The discriminated union is what turned a
             silent content bug into a build failure. */
          if (block.kind === "para") {
            return (
              <p key={block.key} style={PARA}>{t(`${page.ns}.${block.key}`, vars)}</p>
            );
          }
          if (block.kind === "list") {
            return (
              <ul key={block.keys[0]} style={{ paddingLeft: 22, marginTop: 0 }}>
                {block.keys.map((key) => (
                  <li key={key} style={{ marginBottom: 10 }}>{t(`${page.ns}.${key}`, vars)}</li>
                ))}
              </ul>
            );
          }
          if (block.kind === "steps") {
            return (
              <ol key={block.keys[0]} style={{ paddingLeft: 22, marginTop: 0 }}>
                {block.keys.map((key) => (
                  <li key={key} style={{ marginBottom: 10 }}>{t(`${page.ns}.${key}`, vars)}</li>
                ))}
              </ol>
            );
          }
          /* The worked transaction. Four rows, and the two that matter are the
             first and the last: what the brand pays and what the creator
             receives. The middle two exist so the gap between them is not
             something a reader has to take on trust. */
          const commission = commissionFor(block.amount);
          const net = block.amount - commission;
          return (
            <div key="example" className="card" style={{ padding: "6px 20px 14px" }}>
              <div style={ROW}>
                <span>{t(`${page.ns}.exampleAgreed`)}</span>
                <span>{money(block.amount, block.currency)}</span>
              </div>
              <div style={ROW}>
                <span>{t(`${page.ns}.examplePaid`)}</span>
                <span>{money(block.amount, block.currency)}</span>
              </div>
              <div style={ROW}>
                <span className="muted">{t(`${page.ns}.exampleCommission`)}</span>
                <span className="muted">{money(commission, block.currency)}</span>
              </div>
              <div style={LAST_ROW}>
                <span>{t(`${page.ns}.exampleNet`)}</span>
                <span>{money(net, block.currency)}</span>
              </div>
              <p className="muted" style={{ fontSize: 13, margin: "10px 0 0" }}>
                {t(`${page.ns}.exampleNote`)}
              </p>
            </div>
          );
        })}

        {/* The guide joins the two calls to action that were already here.
            Somebody who has read a positioning page and is still deciding
            usually has a mechanical question next, and the guide is where it
            is answered. Its label is the guide's own title, so there is no new
            string to translate. */}
        <div style={{ display: "flex", gap: 12, marginTop: 28, flexWrap: "wrap" }}>
          <Link className="btn btn-primary" to="/register">{t("nav.signup")}</Link>
          <Link className="btn btn-ghost" to="/discover">{t("marketingNav.findCreators")}</Link>
          <Link className="btn btn-ghost" to="/guide">{t("guide.title")}</Link>
        </div>
      </div>
    </Layout>
  );
}
