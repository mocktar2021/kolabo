/* Copy for the content licence: the brand's statement of it on the two screens
   where it names its terms, the panel a creator reads before accepting, and the
   block beside the party blocks on the contract page.

   Owns the licence.* group outright, so it has no ordering constraint against
   i18n.ts: it adds no key to a group another file owns. Its own bundle for the
   reason every other *Strings module has one, which is that the 40 KB i18n.ts
   stays about core app copy.

   PLAIN LANGUAGE AND NOT LEGAL LANGUAGE, WHICH IS THE POINT OF THE FILE. The
   contract clause these three options come from is article 10 of the model
   approved by the founder's counsel, and it is written in the register a
   contract is written in: "licence de rediffusion", "cession des droits
   patrimoniaux", "droits patrimoniaux sur les contenus". A brand choosing
   between them on a form is deciding one thing, which is WHETHER IT MAY LATER
   RUN THIS CONTENT AS A PAID ADVERTISEMENT, and every sentence below that
   describes an option says that in those words. The clause still says what it
   says on the contract; what this file does is make sure nobody agrees to it
   without knowing what they agreed to.

   THREE VOICES, AND THEY ARE NOT INTERCHANGEABLE.

     optionDesc_*   addressed to the brand, on its own form. "You may run it."
     creatorDesc_*  addressed to the creator, on the board and on an
                    invitation, where somebody is about to accept. "The brand
                    may run your content."
     partiesDesc_*  third person naming both sides, on the contract page, which
                    both parties and admins read. "The business may run it."

   The temptation is to write one set and reuse it, and it is the wrong saving:
   a creator reading "vous pouvez rediffuser" about rights they are GRANTING
   has been told the opposite of the truth, on the screen where it costs the
   most. Nine sentences is cheap. Three readers each being told what the option
   means FOR THEM is the entire feature.

   THE THREE OPTIONS ARE NOT EQUAL AND MUST NOT BE WRITTEN AS THOUGH THEY WERE,
   which is the one way this file differs from lib/partyStrings.ts. The three
   forms of party there get descriptions of the same length and the same shape
   because the founder's rule is that the three are equal on Kolabo. These three
   are three different deals at three different prices, and the honest copy says
   so: priceNote and creatorPrice both say outright that option 2 is not priced
   like option 1. What must not happen is one of them being marked as the usual
   choice, or the longest one reading as the serious one.

   NOTHING HERE OFFERS A LIST OF DURATIONS OR TERRITORIES. The hints give
   examples, in the shape of "for example 6 months from publication", and an
   example is not a menu: the value is free text stated by the party and printed
   into the contract verbatim, in the language it was written in. A droplist
   would be Kolabo drafting a clause on a brand's behalf.

   No em dash or en dash in either language. House style, enforced by
   lib/punctuation.test.ts, and the reason several sentences below turn on a
   colon or a full stop where a dash would have been quicker. */
import i18n from "../i18n";

/* THE NO-BREAK SPACE FRENCH TYPOGRAPHY PUTS BEFORE A COLON, as a named constant
   rather than as a character, exactly as lib/partyStrings.ts does it and for the
   same two reasons.

   This bundle sets it at all because this is copy that describes what gets
   printed on a contract, which is the argument that file and lib/legalStrings.ts
   both make. Every other *Strings module here uses an ordinary space and is left
   alone; do not normalise those into this.

   WHY A CONSTANT AND NOT A LITERAL OR AN ESCAPE. A literal U+00A0 is drawn
   exactly like the ordinary space beside it by an editor, a diff and a code
   review, and a space is not a type error, so tsc, vitest and the build all
   stay green over French punctuation that has quietly stopped being French.
   AND A LITERAL \uXXXX ESCAPE CANNOT BE WRITTEN THROUGH THE GITHUB API AT ALL,
   which is how this file was committed. A constant answers both: at the use site
   the interpolation reads as what it is, and it cannot be normalised away by
   anything short of deleting it. Same character at runtime.

   An English string never takes one. */
const NBSP = String.fromCharCode(0x00a0);

const fr = {
  /* THE OPTION NAMES, shared by all three voices. Taken from article 10's own
     headings rather than reinvented, so that somebody holding the contract and
     somebody holding the screen are reading the same three names. The
     descriptions underneath are what differ by reader. */
  name_1: "Option 1. Diffusion par le créateur seul",
  name_2: "Option 2. Licence de rediffusion",
  name_3: "Option 3. Cession des droits patrimoniaux",

  /* The brand's form. French first, like every other bundle here: it is the
     pilot default and three of the five launch markets are francophone. */
  legend: "Droits sur les contenus",
  question: "Que pourrez-vous faire des contenus ?",
  /* The sentence the whole form exists for. Says the decision out loud instead
     of naming the clause. */
  explain: "Vous décidez ici si vous pourrez diffuser ces contenus vous-même, et notamment en faire une publicité payante.",
  printed: `Ce que vous écrivez ici figure mot pour mot dans le contrat, à l'article 10. Le créateur le lit avant d'accepter${NBSP}: c'est une partie de ce qu'il chiffre.`,
  priceNote: "Un créateur ne chiffre pas l'option 2 comme l'option 1. Demandez ce dont vous avez réellement besoin plutôt que le minimum.",

  optionDesc_1: "La publication reste sur les comptes du créateur. Vous pouvez la partager ou la relayer. Vous ne pouvez pas la rediffuser ailleurs, ni en faire une publicité payante.",
  optionDesc_2: "Vous pouvez diffuser les contenus sur vos propres canaux, publicité payante comprise, pendant la durée, sur les territoires et sur les supports que vous indiquez.",
  optionDesc_3: "Les droits patrimoniaux vous sont cédés, pour la durée et les territoires que vous indiquez. Une contrepartie distincte peut être convenue.",

  /* The four free-text fields. Each hint names an example rather than a list,
     because the value is printed into the contract as written. */
  duration: "Durée",
  durationHint: "Écrivez-la comme elle doit figurer au contrat, par exemple 6 mois à compter de la publication.",
  territories: "Territoires",
  territoriesHint: "Les pays ou les zones concernés, par exemple Bénin et Togo, ou monde entier.",
  media: "Supports",
  mediaHint: "Où les contenus passeront, par exemple vos réseaux sociaux, votre site, de l'affichage en magasin.",
  consideration: "Contrepartie distincte",
  considerationHint: "Facultatif. Ce qui est convenu en plus du prix de la prestation, s'il y a lieu.",
  freeText: "Ces précisions sont reprises telles quelles. Kolabo ne propose pas de liste de durées ni de territoires, parce que c'est à vous de les nommer.",

  chooseFirst: "Choisissez d'abord ce que vous pourrez faire des contenus.",
  incomplete: "Complétez ce que cette option demande.",

  /* The read-only panel, on three screens and in two voices. */
  title: "Droits sur les contenus",
  creatorSub: `Ce que la marque a indiqué avant de vous faire cette offre. Lisez-le avant d'accepter${NBSP}: selon l'option, ce n'est pas la même prestation.`,
  creatorDesc_1: "Vous publiez sur vos propres comptes. La marque peut partager ou relayer votre publication, rien de plus.",
  creatorDesc_2: "La marque pourra diffuser vos contenus sur ses propres canaux, publicité payante comprise, dans les limites indiquées ci-dessous.",
  creatorDesc_3: "Vous cédez à la marque les droits patrimoniaux sur ces contenus, pour la durée et les territoires indiqués. Une contrepartie distincte peut être convenue.",
  creatorPrice: "Chiffrez en conséquence. Une publicité payante ou une cession ne valent pas une simple publication.",

  partiesSub: "Ce que l'entreprise a indiqué avant que ce contrat soit généré. C'est l'article 10 du document ci-dessous.",
  partiesDesc_1: "Le créateur publie les contenus sur ses propres comptes. L'entreprise peut uniquement partager ou relayer la publication d'origine.",
  partiesDesc_2: "L'entreprise peut reproduire et diffuser les contenus sur ses propres canaux, publicité payante comprise, dans les limites indiquées.",
  partiesDesc_3: "Le créateur cède à l'entreprise les droits patrimoniaux sur les contenus, pour la durée et les territoires indiqués. Une contrepartie distincte peut être convenue.",

  optionLabel: "Option retenue",
  /* An option this build has never heard of. The stated values are still
     printed, because the brand wrote them and the other side has to be able to
     read them; what is withheld is an explanation this build cannot vouch for. */
  unknownOption: "L'option indiquée ({{option}}) n'est pas une de celles que cette version de l'application sait expliquer. Les précisions de l'entreprise figurent ci-dessous, telles qu'elle les a écrites.",

  /* NOTHING STATED, which is an ordinary state and not a fault: every brief and
     every contract written before this was captured is in it. Two sentences
     rather than one, because what to do about it differs by screen. */
  missingBrief: "La marque n'a pas encore indiqué ce qu'elle pourra faire des contenus. Demandez-le-lui avant d'accepter.",
  missingContract: "Ce contrat a été généré avant que cette précision soit recueillie. L'article 10 du document ci-dessous dit ce qui a été retenu."
};

const en = {
  name_1: "Option 1. The creator posts, nothing more",
  name_2: "Option 2. Licence to run the content",
  name_3: "Option 3. Assignment of the economic rights",

  legend: "Rights in the content",
  question: "What will you be able to do with the content?",
  explain: "You are deciding here whether you may run this content yourself, and in particular whether you may run it as a paid advertisement.",
  printed: "What you write here appears in the contract word for word, at article 10. The creator reads it before accepting, because it is part of what they are pricing.",
  priceNote: "A creator does not price option 2 the way they price option 1. Ask for what you actually need rather than for the least you can ask for.",

  optionDesc_1: "The post stays on the creator's own accounts. You may share it or repost it. You may not run it anywhere else, and you may not turn it into a paid advertisement.",
  optionDesc_2: "You may run the content on your own channels, paid advertising included, for the period, in the territories and on the media you state.",
  optionDesc_3: "The economic rights transfer to you, for the period and the territories you state. A separate payment may be agreed.",

  duration: "Period",
  durationHint: "Write it as it should appear on the contract, for example 6 months from publication.",
  territories: "Territories",
  territoriesHint: "The countries or regions covered, for example Benin and Togo, or worldwide.",
  media: "Media",
  mediaHint: "Where the content will appear, for example your social accounts, your website, in store displays.",
  consideration: "Separate payment",
  considerationHint: "Optional. Whatever is agreed on top of the price of the work, if anything.",
  freeText: "These details are carried over exactly as written. Kolabo offers no list of periods or territories, because naming them is yours to do.",

  chooseFirst: "First choose what you will be able to do with the content.",
  incomplete: "Fill in what this option asks for.",

  title: "Rights in the content",
  creatorSub: "What the brand stated before making you this offer. Read it before you accept, because the three options are not the same job.",
  creatorDesc_1: "You post on your own accounts. The brand may share or repost your post, and nothing more.",
  creatorDesc_2: "The brand will be able to run your content on its own channels, paid advertising included, within the limits stated below.",
  creatorDesc_3: "You transfer the economic rights in this content to the brand, for the period and territories stated. A separate payment may be agreed.",
  creatorPrice: "Price it accordingly. A paid advertisement or a transfer of rights is not the same as a single post.",

  partiesSub: "What the business stated before this contract was generated. It is article 10 of the document below.",
  partiesDesc_1: "The creator posts the content on their own accounts. The business may only share or repost the original.",
  partiesDesc_2: "The business may reproduce and run the content on its own channels, paid advertising included, within the limits stated.",
  partiesDesc_3: "The creator transfers the economic rights in the content to the business, for the period and territories stated. A separate payment may be agreed.",

  optionLabel: "Option stated",
  unknownOption: "The option stated ({{option}}) is not one this version of the app knows how to explain. The business's own details are below, exactly as it wrote them.",

  missingBrief: "The brand has not yet stated what it will be able to do with the content. Ask it before you accept.",
  missingContract: "This contract was generated before this detail was collected. Article 10 of the document below says what was agreed."
};

i18n.addResourceBundle("fr", "translation", { licence: fr }, true, true);
i18n.addResourceBundle("en", "translation", { licence: en }, true, true);
