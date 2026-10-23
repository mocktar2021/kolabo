import i18n from "../i18n";

/* Copy for the content licence: what the brand may do with the creator's
   content, stated by the brand before a contract exists.

   REGISTERED AT RUNTIME, like partyStrings.ts, parityStrings.ts,
   paymentStrings.ts and packageStrings.ts, and for the reason those files
   give: src/strings.ts is 60 KB and a forty-key group lands in it invisibly.
   The consequence is the thing to remember. Every screen that uses a key
   below must import this module FOR ITS SIDE EFFECT, or it renders the raw
   key at the reader. Two components do, and between them they cover all four
   surfaces: components/campaigns/LicenceTermsNotice.tsx (read by a creator on
   the board and on the invitations screen) and
   components/campaigns/LicenceFields.tsx (written by a brand on campaign
   creation).

   ONE FILE FOR BOTH SIDES because they are one fact read from two ends. The
   brand writes a duration and the creator reads a sentence containing it, and
   the two must not drift: the moment the form stops asking for media while
   the sentence goes on promising them, the clause the creator priced is not
   the clause the brand signed. Keeping the pair in one file makes that drift
   a visible diff. The brand's keys carry an l prefix (lf_, lh_) to keep them
   apart from the creator's f_ sentences, which are not labels but finished
   lines.

   THE SENTENCES THAT MATTER are o1, o2_full and o3_full, and they are why
   this copy is worth a file rather than a handful of labels inlined in a
   component.

   o2_full is the whole point of the feature. A creator prices option 2
   differently from option 1, because a video that runs as a paid advert for a
   year is worth more than a post that stays on their own feed, and under the
   old flow they found that out after accepting. So the sentence states it as a
   fact about their own content, in the second person, with the brand's own
   stated duration, territories and media inside it. Not a four row table: a
   table is skippable and this is the one thing on the card that is not.

   o1 EXISTS BECAUSE SILENCE IS AMBIGUOUS. "No redistribution right" and
   "nobody mentioned the licence" look identical if the first one prints
   nothing, and they end in different places: the first is a term the creator
   can price, the second is a contract that cannot be generated. So option 1
   says what it is, and notStated says the other thing.

   notStated AND incomplete BOTH SEND THE READER TO THE BRAND rather than to
   support, because the brand is the only party who can answer. Kolabo does
   not know what licence the brand wants and must not offer to find out: the
   platform records article 10, it is not a party to it.

   NO SENTENCE HERE MAY SUGGEST KOLABO CHECKED ANY OF THIS, the same
   constraint partyStrings.ts carries. A stated duration is self declared
   contract content. formHint says so to the brand in as many words, and
   nothing on the creator's side promises a guarantee the platform does not
   offer.

   THE BRAND'S OWN WORDS ARE NEVER TRANSLATED. verbatim tells the brand that,
   because a duration written in French and read by an anglophone creator will
   arrive in French, and the brand is the only one who can decide whether that
   is a problem. The alternative, a machine translation of a contract term,
   would put a sentence in the document that neither party wrote.

   French first, like the other bundles: three of the five launch markets are
   francophone, and creators are the mobile heavy side of this market. */

const fr = {
  licence: {
    /* Lu par le createur, avant d'accepter. */
    noticeTitle: "Ce que la marque pourra faire de votre contenu",
    notStated: "Cette marque n'a pas encore indiqué ce qu'elle pourra faire de votre contenu. Demandez-le-lui avant d'accepter : cette mention figure sur le contrat, qui ne peut donc pas être généré sans elle.",
    beforeAccept: "Chiffrez votre offre en tenant compte de ces conditions. Un contenu rediffusé en publicité payante ne se paie pas comme une simple publication sur vos comptes.",

    o1: "Cette marque ne pourra pas rediffuser votre contenu. Vous le publiez sur vos propres comptes, et elle pourra seulement partager ou relayer votre publication d'origine.",
    o2_full: "Cette marque pourra rediffuser votre contenu sur ses propres canaux, y compris en publicité payante, pendant {{duration}}, sur {{territories}}, et sur les supports suivants : {{media}}.",
    o2_head: "Cette marque pourra rediffuser votre contenu sur ses propres canaux, y compris en publicité payante.",
    o3_full: "Cette marque acquiert les droits patrimoniaux sur votre contenu, pour {{duration}} et sur {{territories}}. Elle pourra ensuite l'utiliser sans vous le redemander.",
    o3_head: "Cette marque acquiert les droits patrimoniaux sur votre contenu. Elle pourra ensuite l'utiliser sans vous le redemander.",

    /* Des lignes finies, pas des etiquettes de formulaire : elles ne
       s'affichent que lorsque la phrase d'en-tete n'a pas pu etre composee. */
    f_duration: "Durée : {{value}}",
    f_territories: "Territoires : {{value}}",
    f_media: "Supports : {{value}}",
    f_consideration: "Contrepartie distincte : {{value}}",
    incomplete: "La marque n'a pas tout précisé. Demandez-lui ce qui manque avant d'accepter : ce qui n'est pas écrit sur le contrat ne vous protège pas.",

    /* Rempli par la marque, avant qu'un contrat existe. */
    formTitle: "Ce que vous pourrez faire du contenu",
    formHint: "Votre réponse est recopiée telle quelle sur le contrat, et le créateur la lit avant d'accepter. Kolabo ne la vérifie pas : la plateforme écrit ce que vous déclarez.",
    pricing: "Les trois réponses sont acceptées de la même façon. Dites-le ici plutôt qu'après la signature : un créateur chiffre une rediffusion en publicité payante autrement qu'une simple publication.",
    optionLabel: "Droits que vous demandez",
    chooseFirst: "Choisissez une des trois réponses. Rien n'est coché d'avance : c'est à vous de le dire, et non à Kolabo de le supposer.",

    opt_1: "Diffusion par le créateur seul",
    desc_1: "Il publie sur ses comptes. Vous pouvez partager sa publication, pas la rediffuser.",
    opt_2: "Licence de rediffusion",
    desc_2: "Vous rediffusez sur vos canaux, publicité payante comprise.",
    opt_3: "Cession des droits patrimoniaux",
    desc_3: "Les droits vous sont cédés pour la durée et les territoires convenus.",

    lf_duration: "Durée",
    lh_duration: "Par exemple 12 mois à compter de la publication.",
    lf_territories: "Territoires",
    lh_territories: "Par exemple le Bénin et le Togo, ou le monde entier.",
    lf_media: "Supports",
    lh_media: "Par exemple vos réseaux sociaux, votre site, l'affichage en magasin.",
    lf_consideration: "Contrepartie distincte",
    lh_consideration: "Ce que vous payez en plus du prix de la prestation pour cette cession, si vous en convenez d'une.",

    optional: "facultatif",
    incompleteForm: "Complétez les champs demandés pour la réponse choisie.",
    verbatim: "Écrivez-le comme vous voulez le lire sur le contrat. Kolabo ne traduit pas et ne reformule pas ce que vous écrivez ici.",
    /* Toujours sous etiquette : le bloc du createur est redige a la deuxieme
       personne, donc la marque qui relit sa propre campagne doit savoir
       qu'elle lit le texte adresse a l'autre partie. */
    asCreatorSees: "Ce que le créateur lira avant d'accepter :",
  },
};

const en = {
  licence: {
    noticeTitle: "What the brand may do with your content",
    notStated: "This brand has not stated yet what it may do with your content. Ask for it before you accept: that statement appears on the contract, which cannot be generated without it.",
    beforeAccept: "Price your offer with these terms in mind. Content redistributed as paid advertising is not paid for like a single post on your own accounts.",

    o1: "This brand may not redistribute your content. You post it on your own accounts, and the brand may only share or reshare your original post.",
    o2_full: "This brand may redistribute your content on its own channels, including as paid advertising, for {{duration}}, in {{territories}}, and on the following media: {{media}}.",
    o2_head: "This brand may redistribute your content on its own channels, including as paid advertising.",
    o3_full: "This brand takes the economic rights in your content, for {{duration}} and in {{territories}}. It may then use the content without asking you again.",
    o3_head: "This brand takes the economic rights in your content. It may then use the content without asking you again.",

    f_duration: "Duration: {{value}}",
    f_territories: "Territories: {{value}}",
    f_media: "Media: {{value}}",
    f_consideration: "Separate consideration: {{value}}",
    incomplete: "The brand has not stated all of it. Ask for what is missing before you accept: what is not written on the contract does not protect you.",

    formTitle: "What you may do with the content",
    formHint: "Your answer is copied onto the contract word for word, and the creator reads it before accepting. Kolabo does not verify it: the platform writes down what you state.",
    pricing: "All three answers are accepted the same way. Say it here rather than after signing: a creator prices redistribution as paid advertising differently from a single post.",
    optionLabel: "Rights you are asking for",
    chooseFirst: "Choose one of the three answers. Nothing is ticked for you: this is yours to state, not Kolabo's to assume.",

    opt_1: "The creator posts, and only the creator",
    desc_1: "They post on their own accounts. You may share that post, not redistribute it.",
    opt_2: "Redistribution licence",
    desc_2: "You redistribute on your own channels, paid advertising included.",
    opt_3: "Assignment of economic rights",
    desc_3: "The rights pass to you for the duration and territories agreed.",

    lf_duration: "Duration",
    lh_duration: "For example 12 months from the date of posting.",
    lf_territories: "Territories",
    lh_territories: "For example Benin and Togo, or worldwide.",
    lf_media: "Media",
    lh_media: "For example your social channels, your website, in-store display.",
    lf_consideration: "Separate consideration",
    lh_consideration: "What you pay on top of the fee for this assignment, if you agree one.",

    optional: "optional",
    incompleteForm: "Fill in the fields asked for the answer you chose.",
    verbatim: "Write it the way you want to read it on the contract. Kolabo does not translate it and does not reword it.",
    asCreatorSees: "What the creator reads before accepting:",
  },
};

i18n.addResourceBundle("fr", "translation", fr, true, true);
i18n.addResourceBundle("en", "translation", en, true, true);
