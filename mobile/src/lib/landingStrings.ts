import i18n from "../i18n";

/* Copy for the pre-auth landing carousel — the first screen a new install
   sees, before Login and before Register.

   REGISTERED AT RUNTIME, exactly like lib/paymentStrings.ts and
   lib/packageStrings.ts, and for the same reason those two give: src/
   strings.ts is 60 KB, and a self-contained feature's forty keys land there
   invisibly. The cost of that choice is real and worth stating plainly — a
   screen that uses these keys MUST import this module for its side effect, or
   it renders raw key names. LandingScreen.tsx does, at the top of its
   imports, and nothing else uses the landing.* group.

   French first, like the other two bundles: it is the pilot default and three
   of the five launch markets are francophone.

   NAMES AND NUMBERS IN THE MOCK CARDS ARE ILLUSTRATIONS, not claims. They are
   invented people on invented deals, drawn in the shape of the real product
   surfaces, the same way web/src/pages/Landing.tsx draws its workflow
   vignettes. That is why the cards are hidden from screen readers in
   components/landing.tsx: what the slide actually promises is in the headline
   and the body underneath, and those are the sentences that have to be true.
   The only figures here are 10 000 XOF and a follower count on a person who
   does not exist.

   THAT NOTE USED TO BE THE WHOLE OF IT, and a comment and an accessibility
   attribute are the two places the person holding the phone cannot read.
   artExample is the same sentence said out loud, under every card. Two
   claims went with it, because a caption does not undo a sentence that
   asserts something untrue: s3CardChip put a "verified review" badge over a
   review Kolabo never took, and s3When said the collaboration behind it was
   real. Kolabo has run no collaborations, so the badge is deleted and s3When
   now names the card for what it is. */

const fr = {
  /* Splash. Two lines because it is set as two lines: the first names the
     market, the second names the span of the product. */
  taglineA: "Le marketing d'influence en Afrique,",
  taglineB: "de la recherche au paiement.",

  /* The caption SlideArt draws under every mock card. One key for all three
     slides because all three are drawings: an invented creator, an invented
     escrow, an invented review. It sits on the panel rather than inside the
     white card, so it reads as a label on the picture and not as one more
     line of the picture. */
  artExample: "Exemple",

  /* The headlines are split A / accent / B so the teal phrase can be its own
     <Text> inside the sentence — the same three-part shape web's hero uses
     (landing.heroA / heroAccent / heroB). Splitting is not optional here: a
     single string with markup in it cannot be styled, and a single string
     without it loses the emphasis the design is built on. */
  s1HeadA: "Trouvez les créateurs qui font ",
  s1HeadAccent: "grandir",
  s1HeadB: " votre marque.",
  s1Body:
    "Recherchez par niche, pays et audience parmi des créateurs africains. La recherche est gratuite.",
  s1Verified: "Connecté",
  s1Meta: "283k abonnés · Cotonou, BJ",
  s1Chip1: "Mode",
  s1Chip2: "Beauté",
  s1Chip3: "Tech",
  s1CardCta: "Voir le profil",

  s2HeadA: "Des paiements ",
  s2HeadAccent: "protégés",
  s2HeadB: ", du brief à la livraison.",
  s2Body:
    "Signez le contrat et payez en séquestre. Les fonds ne sont libérés qu'une fois la collaboration validée, par Mobile Money.",
  s2CardTitle: "Paiement en séquestre",
  s2CardChip: "Protégé",
  s2CardSub: "Fonds bloqués jusqu'à validation",
  s2Step1: "Contrat signé",
  s2Step2: "Fonds en séquestre",
  s2Step3: "En attente de validation",

  s3HeadA: "Tout au même endroit, ",
  s3HeadAccent: "en confiance",
  s3HeadB: ".",
  s3Body:
    "Messagerie, contrats et avis vérifiés réunis sur une seule plateforme. Suivez chaque collaboration, de la découverte à l'avis final.",
  s3Rating: "5,0",
  s3Quote: "« Collaboration fluide et paiement rapide. Une créatrice au top. »",
  s3Who: "Awa Koné · Marque Beauté",
  s3When: "Avis d'exemple",
  s3Chip1: "Messagerie",
  s3Chip2: "Contrats",
  s3Chip3: "Avis",

  ctaRegister: "Créer un compte",
  ctaLogin: "Se connecter",

  /* Spoken, never drawn. The dots are 6 dp wide and carry no label of their
     own, so the only thing a screen reader has to go on is this. */
  a11ySlide: "Écran {{n}} sur {{total}}",
  a11yGoToSlide: "Aller à l'écran {{n}}",
};

const en = {
  taglineA: "Influencer marketing in Africa,",
  taglineB: "from search to payment.",

  artExample: "Example",

  s1HeadA: "Find the creators who make your brand ",
  s1HeadAccent: "grow",
  s1HeadB: ".",
  s1Body:
    "Search by niche, country and audience across African creators. Searching is free.",
  s1Verified: "Connected",
  s1Meta: "283k followers · Cotonou, BJ",
  s1Chip1: "Fashion",
  s1Chip2: "Beauty",
  s1Chip3: "Tech",
  s1CardCta: "View profile",

  s2HeadA: "Payments that stay ",
  s2HeadAccent: "protected",
  s2HeadB: ", from brief to delivery.",
  s2Body:
    "Sign the contract and pay into escrow. The funds are released only once the collaboration is approved, and they move by Mobile Money.",
  s2CardTitle: "Escrow payment",
  s2CardChip: "Protected",
  s2CardSub: "Funds held until approval",
  s2Step1: "Contract signed",
  s2Step2: "Funds in escrow",
  s2Step3: "Awaiting approval",

  s3HeadA: "It all lives in one place, ",
  s3HeadAccent: "built on trust",
  s3HeadB: ".",
  s3Body:
    "Messaging, contracts and verified reviews on a single platform. Follow every collaboration, from the first search to the final review.",
  s3Rating: "5.0",
  s3Quote: "“Smooth collaboration, fast payment. A brilliant creator.”",
  s3Who: "Awa Koné · Beauty brand",
  s3When: "Example review",
  s3Chip1: "Messaging",
  s3Chip2: "Contracts",
  s3Chip3: "Reviews",

  ctaRegister: "Create an account",
  ctaLogin: "Log in",

  a11ySlide: "Screen {{n}} of {{total}}",
  a11yGoToSlide: "Go to screen {{n}}",
};

i18n.addResourceBundle("fr", "translation", { landing: fr }, true, true);
i18n.addResourceBundle("en", "translation", { landing: en }, true, true);
