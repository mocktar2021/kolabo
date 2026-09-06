/* The open board, brief targeting, and the brand-facing landing section that
   explains the flow. Registered as a resource bundle so the 40 KB i18n.ts
   stays focused on the core app copy — the same arrangement the cart, the
   disputes queue, the admin console, the account settings and the two money
   screens use.

   nav.board and the landing.brief* keys are deep-merged into the groups
   i18n.ts and marketingStrings.ts own: addResourceBundle runs with deep=true
   and overwrite=true, and main.tsx imports this after both, so the keys join
   the existing groups rather than replacing them. */
import i18n from "../i18n";

const frBoard = {
  title: "Briefs ouverts",
  sub: "Les campagnes publiées auxquelles n'importe quel créateur peut postuler, sans invitation.",

  /* Dit en haut de la page, parce qu'un classement silencieux est un
     classement sur lequel les créateurs inventent des théories. Le score
     range, il n'exclut pas. */
  rankHint: "Les briefs qui correspondent le mieux à votre profil sont placés en premier. Ce n'est qu'un classement : vous pouvez postuler à tous les briefs de cette page, y compris à ceux qui ne vous correspondent pas.",

  /* Les filtres du créateur. À ne pas confondre avec le ciblage de la marque :
     l'un réduit la liste, l'autre en décide l'ordre. */
  filters: "Filtres",
  budgetMin: "Budget minimum",
  budgetMax: "Budget maximum",
  niche: "Niche",
  nicheAll: "Toutes les niches",
  country: "Pays",
  countryAll: "Tous les pays",
  platform: "Plateforme",
  platformAll: "Toutes les plateformes",
  deadlineBefore: "Échéance avant le",
  apply2: "Filtrer",
  reset: "Réinitialiser",
  filterNote: "Les filtres réduisent la liste ; ils n'en changent pas l'ordre. Ce qui reste affiché est toujours classé par correspondance avec votre profil.",

  matchStrong: "Correspond à votre profil",
  matchNone: "Ouvert à tous",
  matchAria: "Correspondance {{n}} sur {{max}}",

  unknownBrand: "Marque",
  deadline: "Échéance",
  noDeadline: "Sans échéance",
  deliverables: "Livrables",
  noDeliverables: "Livrables à préciser",

  apply: "Postuler",
  applyCancel: "Annuler",
  applySend: "Envoyer ma proposition",
  applyRate: "Votre tarif",
  applyCurrency: "Devise",
  applyDays: "Délai (jours)",
  applyNote: "Un mot sur votre proposition (facultatif)",
  applyNotePlaceholder: "Ce que vous proposez, et pourquoi ce tarif.",
  applySent: "Votre proposition a été envoyée. La marque la verra avec les autres offres de sa campagne.",

  applied: "Déjà postulé",
  appliedHint: "Vous avez déjà proposé vos conditions ici. Pour les modifier, envoyez une nouvelle version depuis la négociation plutôt que de postuler une seconde fois.",
  invited: "Vous êtes invité",
  invitedHint: "Ce brief vous a été adressé directement. Répondez-y depuis vos invitations, là où se trouve l'offre.",
  invitedLink: "Voir mes invitations",

  empty: "Aucun brief ouvert pour l'instant.",
  emptyHint: "Un brief apparaît ici quand une marque publie une campagne et l'ouvre aux candidatures. En attendant, les invitations qui vous sont adressées arrivent dans Invitations.",

  /* L'ÉTAT VIDE FILTRÉ, et il doit dire une chose précise qui ressemble à un
     bug : les filtres Niche et Pays lisent le CIBLAGE de la marque. Un brief
     qui ne vise personne en particulier — celui-là même qui est ouvert à tout
     le monde et qui apparaît sur tous les tableaux non filtrés — ne
     correspond donc à aucune niche et à aucun pays, et disparaît. Le seul
     moyen de le revoir est d'élargir : la phrase pointe vers le bouton. */
  emptyFiltered: "Aucun brief ne correspond à ces filtres.",
  emptyFilteredHint: "Attention aux filtres Niche et Pays : ils lisent le ciblage de la marque, donc ils masquent aussi les briefs qui ne visent personne en particulier, et ce sont justement ceux qui sont ouverts à tout le monde. Élargissez vos filtres ou réinitialisez-les pour les revoir.",

  loadFailed: "Impossible de charger les briefs ouverts pour l'instant."
};

const enBoard = {
  title: "Open briefs",
  sub: "Published campaigns any creator can apply to, without an invitation.",

  rankHint: "The briefs that best fit your profile are placed first. It is only a ranking: you can apply to every brief on this page, including the ones that do not match you.",

  filters: "Filters",
  budgetMin: "Minimum budget",
  budgetMax: "Maximum budget",
  niche: "Niche",
  nicheAll: "All niches",
  country: "Country",
  countryAll: "All countries",
  platform: "Platform",
  platformAll: "All platforms",
  deadlineBefore: "Deadline before",
  apply2: "Filter",
  reset: "Reset",
  filterNote: "Filters narrow the list; they do not change its order. Whatever is left is still ranked by how well it fits your profile.",

  matchStrong: "Fits your profile",
  matchNone: "Open to everyone",
  matchAria: "Match {{n}} out of {{max}}",

  unknownBrand: "Brand",
  deadline: "Deadline",
  noDeadline: "No deadline",
  deliverables: "Deliverables",
  noDeliverables: "Deliverables to be confirmed",

  apply: "Apply",
  applyCancel: "Cancel",
  applySend: "Send my proposal",
  applyRate: "Your rate",
  applyCurrency: "Currency",
  applyDays: "Timeline (days)",
  applyNote: "A word about your proposal (optional)",
  applyNotePlaceholder: "What you are offering, and why this rate.",
  applySent: "Your proposal has been sent. The brand will see it alongside the other offers on its campaign.",

  applied: "Already applied",
  appliedHint: "You have already offered your terms here. To change them, send a new version from the negotiation rather than applying a second time.",
  invited: "You are invited",
  invitedHint: "This brief was addressed to you directly. Answer it from your invitations, where the offer is.",
  invitedLink: "See my invitations",

  empty: "No open briefs yet.",
  emptyHint: "A brief appears here when a brand publishes a campaign and opens it to applications. In the meantime, invitations addressed to you arrive under Invitations.",

  emptyFiltered: "No brief matches these filters.",
  emptyFilteredHint: "Watch the Niche and Country filters: they read the brand's targeting, so they also hide briefs that target nobody in particular, and those are exactly the ones open to everyone. Widen your filters or reset them to see those again.",

  loadFailed: "Open briefs could not be loaded right now."
};

const frTarget = {
  open: "Ouvrir aux candidatures",
  openHint: "Votre brief apparaît sur le tableau des briefs ouverts, et n'importe quel créateur peut vous proposer ses conditions.",

  legend: "Ciblage",
  /* LA RÈGLE PRODUIT, dite à l'écran et pas seulement dans le code : le
     ciblage classe, il n'exclut pas. Une marque qui croit avoir posé un
     filtre dur se demanderait pourquoi elle reçoit des candidatures hors
     cible — et refuserait une candidature au lieu de la lire. */
  explain: "Le ciblage classe qui voit votre brief en premier. Il ne bloque personne : un créateur hors cible verra quand même votre brief et pourra postuler, et vous restez libre de décliner.",

  categories: "Niches",
  countries: "Pays",
  minFollowers: "Audience minimale",
  maxFollowers: "Audience maximale",
  followersHint: "Laissez vide pour ne pas borner."
};

const enTarget = {
  open: "Open to applications",
  openHint: "Your brief appears on the open board, and any creator can offer you their terms.",

  legend: "Targeting",
  explain: "Targeting ranks who sees your brief first. It blocks nobody: a creator outside your target still sees the brief and can still apply, and you remain free to decline.",

  categories: "Niches",
  countries: "Countries",
  minFollowers: "Minimum audience",
  maxFollowers: "Maximum audience",
  followersHint: "Leave empty for no bound."
};

/* The brand-facing half of the same story, on the landing page.

   NOT ONE NUMBER IN IT, and that is deliberate rather than an oversight. We
   do not know how many creators are on the platform, how fast a brief fills,
   or what a typical application looks like, and a marketing figure nobody can
   stand behind is the fastest way to lose a brand on its second visit. The
   only digits this section renders are the step ordinals the shared
   .step-grid draws, which are structure and not a claim. */
const frLanding = {
  briefTitle: "Publiez un brief, recevez des candidatures",
  briefSub: "L'autre sens du marché : au lieu de contacter les créateurs un par un, décrivez ce que vous cherchez et laissez-les venir à vous.",

  brief1t: "Définissez votre cible",
  brief1d: "Niche, localisation, taille d'audience. Ce ciblage classe qui voit votre brief en premier ; il n'empêche personne de postuler.",

  brief2t: "Publiez votre brief",
  brief2d: "Images, exigences, budget, échéance. C'est le document sur lequel les créateurs se prononcent.",

  brief3t: "Les créateurs postulent",
  brief3d: "Ils proposent leur tarif et leur délai. Vous choisissez, vous négociez, vous signez. Le tout sans quitter Kolabo."
};

const enLanding = {
  briefTitle: "Post a brief, receive applications",
  briefSub: "The market running the other way: instead of contacting creators one at a time, describe what you are looking for and let them come to you.",

  brief1t: "Define your target",
  brief1d: "Niche, location, audience size. This targeting ranks who sees your brief first; it stops nobody from applying.",

  brief2t: "Publish your brief",
  brief2d: "Images, requirements, budget, deadline. It is the document creators price against.",

  brief3t: "Creators apply",
  brief3d: "They propose their rate and their timeline. You choose, you negotiate, you sign. All without leaving Kolabo."
};

i18n.addResourceBundle(
  "fr",
  "translation",
  { board: frBoard, target: frTarget, landing: frLanding, nav: { board: "Briefs" } },
  true,
  true
);
i18n.addResourceBundle(
  "en",
  "translation",
  { board: enBoard, target: enTarget, landing: enLanding, nav: { board: "Briefs" } },
  true,
  true
);
