/* Copy for the party-details form, the card that links to it from the profile,
   and the party block on the contract page.

   Owns the party.* group outright, so it has no ordering constraint against
   i18n.ts: it adds no key to a group another file owns. Its own bundle for the
   reason every other *Strings module has one, which is that the 40 KB i18n.ts
   stays about core app copy.

   notVerified IS THE STRING THIS FILE EXISTS FOR. A party block is
   SELF-DECLARED CONTRACT CONTENT: the founder settled on 3 October that no
   identity documents are collected, and nothing about party capture changed
   that. Kolabo records what each side states about itself and checks none of
   it, exactly as a paper contract records what the parties write at the top of
   it. So every screen that shows a block shows that sentence, no string below
   calls a party verified, approved or confirmed, and nothing here may become a
   badge. If a future reviewer softens this copy, the product starts implying a
   check it does not perform, on the one screen where that matters.

   equalForms AND THE THREE typeDesc_* STRINGS CARRY THE OTHER RULE, which is
   the founder's: businesses on Kolabo are NOT limited to registered ones. The
   three descriptions are the same length and the same shape, none of them
   apologises for anything, and equalForms says outright that the three forms
   sign contracts and get paid the same way. Rewriting one of them means
   rewriting all three, or the shortest branch starts reading as the lesser
   one.

   THREE LABELS FOR ONE FIELD. legalNameCompany, legalNamePerson and
   legalNameAssociation are the same request key spelled for three readers,
   which is why lib/party.ts names a labelKey per branch instead of deriving
   one from the field name.

   No em dash or en dash in either language. House style, enforced by
   lib/punctuation.test.ts, and the reason several sentences below turn on a
   colon or a full stop where a dash would have been quicker. */
import i18n from "../i18n";

/* THE NO-BREAK SPACE FRENCH TYPOGRAPHY PUTS BEFORE A COLON, as a named
   constant rather than as a character.

   This bundle sets it at all because this is the copy that describes what gets
   printed on a contract, which is the same argument lib/legalStrings.ts makes
   for the privacy policy and the terms. Every other *Strings module here uses
   an ordinary space and is left alone; do not normalise those into this.

   WHY A CONSTANT AND NOT THE INLINE UNICODE ESCAPE THAT FILE USES. Its
   objection is to the LITERAL character, and the objection is sound: a literal
   U+00A0 is drawn exactly like the ordinary space beside it by an editor, a
   diff and a code review, a space is not a type error, so tsc, vitest and the
   build all stay green over French punctuation that has quietly stopped being
   French. legalStrings.ts lost its own more than once that way and the only
   thing that ever noticed was a byte count. A constant answers that better
   than an escape does: at the use site the interpolation reads as what it is
   instead of as six characters a reader has to decode, and it cannot be
   normalised away by anything short of deleting it. Same character at runtime.

   Built with String.fromCharCode for the reason lib/punctuation.test.ts builds
   its em dash and en dash that way: a file that talks about an invisible
   character should not contain one.

   Three sentences below take one, all French. An English string never does. */
const NBSP = String.fromCharCode(0x00a0);

const fr = {
  /* The form. French first, like every other bundle here: it is the pilot
     default and three of the five launch markets are francophone. */
  title: "Qui vous êtes sur un contrat",
  sub: "Ces informations sont celles qui figureront sur chaque contrat que vous signez sur Kolabo, et que l'autre partie lira.",
  notVerified: `Kolabo ne vérifie pas ces informations${NBSP}: vous les déclarez vous-même, comme vous le feriez en haut d'un contrat papier. Rien ici n'est contrôlé et rien ici ne donne de badge.`,
  missing: "Vous n'avez pas encore renseigné ces informations. Un contrat ne peut pas être généré tant qu'elles manquent, d'un côté comme de l'autre.",

  /* The first question, which decides the rest of the form. */
  typeQuestion: "Sous quelle forme contractez-vous ?",
  equalForms: `Les trois formes se valent sur Kolabo${NBSP}: chacune signe des contrats et reçoit des paiements de la même manière.`,
  /* Said beside the question rather than after a refusal. The server refuses a
     change with party_type_immutable once a contract exists, and the sentence
     for that code is in lib/errorMessages.ts; this is the same rule said in
     advance, which is where somebody can still act on it. */
  typeLocked: `Une fois qu'un contrat a été généré, cette forme ne change plus${NBSP}: un contrat signé doit continuer de se lire comme ce qu'il était. Écrivez au support si votre situation a changé.`,

  type_registered_company: "Entreprise immatriculée",
  typeDesc_registered_company: "Une société ou un établissement inscrit à un registre du commerce.",
  type_sole_trader: "En nom propre",
  typeDesc_sole_trader: "Vous contractez sous votre propre nom, sans structure immatriculée.",
  type_association: "Association ou ONG",
  typeDesc_association: "Une association déclarée, une ONG ou une structure équivalente.",

  /* The fields. Three spellings of the same request key, then the rest. */
  legalNameCompany: "Dénomination sociale",
  legalNamePerson: "Nom et prénoms",
  legalNameAssociation: "Nom de l'association",
  legalForm: "Forme juridique",
  legalFormHint: "Par exemple SARL, SA, établissement.",
  registrationNumber: "Numéro d'immatriculation",
  registrationNumberHint: "RCCM ou l'équivalent dans votre pays.",
  taxIdentifier: "Identifiant fiscal",
  taxIdentifierHint: "IFU, NIF ou l'équivalent dans votre pays.",
  taxIdentifierOptionalHint: "Facultatif. IFU, NIF ou l'équivalent, si vous en avez un.",
  address: "Adresse",
  addressHint: "L'adresse complète, telle qu'elle doit figurer sur le contrat.",
  country: "Pays",
  countryChoose: "Choisissez un pays",
  representativeName: "Nom du représentant",
  representativeNameHint: "La personne qui signe pour la structure.",
  representativeCapacity: "Qualité du représentant",
  representativeCapacityHint: "Par exemple gérant, directrice générale, présidente.",

  save: "Enregistrer",
  saved: "Vos informations sont enregistrées.",
  incomplete: "Complétez les champs demandés pour cette forme.",
  backToProfile: "Retour au profil",

  /* The card on the profile page, which is how this screen is found. The three
     bodies are the three things the card can honestly say: filled in, not
     filled in, and we could not ask. */
  cardTitle: "Vos informations contractuelles",
  cardBodySet: "Renseignées. Elles figureront sur vos prochains contrats, telles que vous les avez écrites.",
  cardBodyMissing: "Pas encore renseignées. Un contrat ne peut pas être généré tant qu'elles manquent.",
  cardBodyUnknown: "Le nom, l'adresse et les identifiants qui figureront sur vos contrats. Ils se renseignent sur leur propre écran.",
  cardOpen: "Renseigner mes informations",
  cardEdit: "Modifier mes informations",

  /* The block on the contract page. Visible to the two parties and to admins,
     and nowhere else: not on a public profile, not in search. */
  contractTitle: "Les parties",
  contractSub: "Ce que chaque partie a déclaré sur elle-même au moment où ce contrat a été généré. Kolabo ne vérifie pas ces informations.",
  sideBusiness: "Entreprise",
  sideCreator: "Créateur",
  sideMissing: "Cette partie n'avait pas renseigné ses informations.",
  legacy: "Ce contrat a été généré avant que ces informations soient recueillies. Les identifiants des deux parties restent dans le document ci-dessous."
};

const en = {
  title: "Who you are on a contract",
  sub: "These details are what will appear on every contract you sign on Kolabo, and what the other party will read.",
  notVerified: "Kolabo does not check these details: you state them yourself, the way you would at the top of a paper contract. Nothing here is verified and nothing here earns a badge.",
  missing: "You have not filled these in yet. A contract cannot be generated while either side's details are missing.",

  typeQuestion: "In what form do you contract?",
  equalForms: "The three forms are equal on Kolabo: each one signs contracts and gets paid the same way.",
  typeLocked: "Once a contract has been generated, this form no longer changes: a signed contract has to keep reading as what it was. Write to support if your situation has changed.",

  type_registered_company: "Registered company",
  typeDesc_registered_company: "A company or a firm entered in a companies register.",
  type_sole_trader: "Sole trader",
  typeDesc_sole_trader: "You contract under your own name, with no registered entity.",
  type_association: "Association or NGO",
  typeDesc_association: "A declared association, an NGO or an equivalent body.",

  legalNameCompany: "Registered company name",
  legalNamePerson: "Full name",
  legalNameAssociation: "Name of the association",
  legalForm: "Legal form",
  legalFormHint: "For example SARL, SA, Ltd.",
  registrationNumber: "Registration number",
  registrationNumberHint: "An RCCM entry or the equivalent in your country.",
  taxIdentifier: "Tax identifier",
  taxIdentifierHint: "IFU, NIF or the equivalent in your country.",
  taxIdentifierOptionalHint: "Optional. IFU, NIF or the equivalent, if you have one.",
  address: "Address",
  addressHint: "The full address, as it should appear on the contract.",
  country: "Country",
  countryChoose: "Choose a country",
  representativeName: "Representative name",
  representativeNameHint: "The person who signs for the entity.",
  representativeCapacity: "Representative capacity",
  representativeCapacityHint: "For example manager, managing director, president.",

  save: "Save",
  saved: "Your details are saved.",
  incomplete: "Fill in the fields this form asks for.",
  backToProfile: "Back to the profile",

  cardTitle: "Your contract details",
  cardBodySet: "Filled in. They will appear on your next contracts, exactly as you wrote them.",
  cardBodyMissing: "Not filled in yet. A contract cannot be generated while they are missing.",
  cardBodyUnknown: "The name, address and identifiers that will appear on your contracts. They are filled in on their own screen.",
  cardOpen: "Fill in my details",
  cardEdit: "Change my details",

  contractTitle: "The parties",
  contractSub: "What each party stated about itself when this contract was generated. Kolabo does not check these details.",
  sideBusiness: "Business",
  sideCreator: "Creator",
  sideMissing: "This party had not filled in their details.",
  legacy: "This contract was generated before these details were collected. Both parties' identifiers are still in the document below."
};

i18n.addResourceBundle("fr", "translation", { party: fr }, true, true);
i18n.addResourceBundle("en", "translation", { party: en }, true, true);
