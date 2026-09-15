/* THE PRIVACY POLICY, in both languages.

   Its own bundle for the reason every other *Strings module has one — the
   40 KB i18n.ts stays about core app copy — and for one more that is specific
   to this document: it is a legal undertaking that a lawyer has to read,
   correct and re-read, and a legal document is easier to hand over as one
   file than as a diff scattered through the app's copy.

   IT ALSO ADDS footer.privacy to the footer.* group marketingStrings.ts owns.
   Same arrangement notificationStrings has with nav.* and socialStrings has
   with profile.*: addResourceBundle runs with deep=true and overwrite=true,
   and main.tsx imports this AFTER marketingStrings, so the key joins that
   group rather than replacing it.

   NOTHING IN THE APP IMPORTS THIS MODULE. main.tsx imports it for the side
   effect and nothing else, which is why the document OUTLINE — which heading
   comes before which paragraph — lives in pages/LegalPage.tsx rather than
   here. App.tsx imports that page, main.tsx imports "./App" on its first
   line, and an import chain from App.tsx into any *Strings module would
   evaluate that bundle before "./lib/marketingStrings" further down the file:
   exactly the ordering the paragraph above depends on.

   FRENCH TYPOGRAPHY, AND IT IS DIFFERENT FROM THE REST OF THE APP. The French
   below sets the curly apostrophe and a non-breaking space before : ; ? and !
   No other bundle here does — they all use the straight apostrophe and an
   ordinary space. The divergence is deliberate and confined to this document:
   it is what a regulator, an app-store reviewer and a lawyer read, and it is
   the one place in the product where French punctuation is worth the trouble.
   Do not normalise it away.

   THE FIFTEEN NON-BREAKING SPACES BELOW ARE WRITTEN AS \\u00A0, ON PURPOSE.
   They used to be literal U+00A0 characters, and a literal one is invisible:
   an editor, a diff and a code review all draw it exactly like the ordinary
   space beside it, and nothing in the toolchain says when one is lost. A
   space is not a type error, so tsc, vitest and the build all stay green
   over French punctuation that has quietly stopped being French. This file
   lost all fifteen that way more than once while being committed, and the
   only thing that ever noticed was a byte count. The escape is the same
   character at runtime, it cannot be normalised away by anything short of an
   edit, and it shows up in a diff. Keep writing new ones as \\u00A0. All
   fifteen are on /legal/privacy.

   THE REGISTRATION IDENTIFIERS AND THE POSTAL ADDRESS ARE THE SAME STRING IN
   BOTH LANGUAGES. RB/COT/26 A 119654 and 1200900488800 identify a company in
   a register; they are not words. The address is left unlocalised for the
   same reason and to match lib/countries.ts, which spells every country in
   English in both bundles.

   SO IS THE ONE URL, AND ITS href IS NOT IN THIS FILE AT ALL. whoLink and
   contactRegistrationLink hold the VISIBLE TEXT of a link — the address
   without its scheme — and the https:// target lives beside the block in
   pages/LegalPage.tsx. A URL inside translated copy is a URL a translator can
   mangle, and it would have to be written identically in both bundles anyway,
   which is the same argument as the identifiers above. The page renders it
   through a declared `link` block; nothing here is parsed.

   THE ADDRESS CARRIES NO TRAILING SLASH, and that changed with this note. The
   policy used to print mocktar.com/legal/entities/ as plain text in four
   places. BOTH FORMS RESOLVE TODAY: /legal/entities and /legal/entities/ were
   both fetched and both returned the "Company details" page, and a 404
   reported against the sibling /legal/privacy/ did not reproduce either. So
   this is NOT the repair of a broken link, and nobody should record it as
   one. It is the canonical form — the one the site's own navigation uses —
   rather than a form that depends on the host continuing to forgive a slash,
   in the document where a reviewer follows the link to confirm who they are
   dealing with.

   WHY THE PRIVACY POLICY SHIPS ALONE, WITHOUT THE TERMS OF SERVICE. The two
   documents were drafted together, and the Terms are blocked on one thing:
   which entity contracts with users, and under which law, is an open founder
   decision, and a clause naming the wrong forum is a representation made to
   every user who accepted it while a missing one is merely incomplete. That
   blocker lives entirely inside the Terms. Nothing in the privacy policy
   turns on the governing-law answer, so this document goes live now and the
   Terms follow when the answer arrives. There is therefore NO GOVERNING-LAW
   CLAUSE ANYWHERE IN THIS FILE, and there should not be one — the clause
   belongs to /legal/terms, which does not exist yet.

   Every factual claim below was checked against the repo at main @ c447e4ad
   and re-checked for the email identity flip: the EMAIL ADDRESS as the login
   identity with the phone number nullable and optional
   (auth/models.py::User), hashed passwords (User.password_hash), expiring
   single-use codes
   (OtpChallenge), images in the database (MediaAsset.data), audience figures
   from the platforms' own APIs (profiles/enrichment.py), AI-drafted bios
   (profiles/bio_ai.py), documents encrypted at rest
   (VerificationDocument.ciphertext), escrow and payouts
   (payments/gateway_models.py) and the masked payout number
   (payouts.py::_method_out). If any of those change, this file changes with
   them. Two claims did not survive that check a second time; see the note
   above collectVerify. A third was wrong in the OTHER direction — it denied
   the platform a feature it has — see the note on deletion below.

   Retention periods, a DPO and any certification are absent because nothing
   implements them. Do not add a table of periods to look thorough.

   SELF-SERVICE ACCOUNT DELETION USED TO BE ON THAT LIST AND DOES NOT BELONG
   THERE: it is implemented. DELETE /auth/me
   (auth/service.py::delete_account) takes the CURRENT PASSWORD rather than
   the bearer token alone — a stolen session must not be enough to erase
   somebody's livelihood — and hard-deletes the account and its children in
   one transaction. It does so ONLY while the account has no contracts and no
   escrows in either role; otherwise it refuses with 409
   auth_account_has_history, and closing the account becomes a support
   workflow, because counterparties keep their own contract and review history
   and money trails are never erased. rightsEdit says both halves of that.

   IT SAYS "ON THE KOLABO WEBSITE" AND MUST NOT BE WIDENED TO "IN THE APP".
   web/src/pages/Account.tsx calls that endpoint; mobile's AccountScreen.tsx
   only reads and PATCHes /auth/me, so there is no delete control in the
   mobile apps. Widen the sentence on the day one exists, and not before. */
import i18n from "../i18n";

const fr = {
  legal: {
    /* La date est interpolée depuis LEGAL_EFFECTIVE_DATE dans
       pages/LegalPage.tsx, une seule constante pour les deux langues. */
    effective: "En vigueur le {{date}}",

    privacy: {
      title: "Politique de confidentialité",

      intro: "Kolabo est exploité par Mocktar Technologies, responsable du traitement. Cette politique explique ce que nous collectons lorsque vous utilisez Kolabo, pourquoi, qui d’autre y a accès, et ce que vous pouvez nous demander à ce sujet. Elle couvre le site web et les applications mobiles Kolabo. Elle ne couvre pas mocktar.com ni nos autres produits, qui ont leurs propres politiques.",

      whoTitle: "Qui nous sommes",
      who: "Mocktar Technologies, C 1357 Houeyiho, 07BP91, Cotonou, Benin. RCCM RB/COT/26 A 119654, IFU 1200900488800. Les informations d’immatriculation complètes, y compris celles de notre entité aux États-Unis, sont publiées à l’adresse suivante\\u00A0:",
      whoLink: "mocktar.com/legal/entities",

      collectTitle: "Ce que nous collectons",
      collectAccount: "**Pour créer votre compte.** Votre adresse e-mail, qui vous sert à vous connecter et qui est le seul identifiant que nous exigeons. Un mot de passe, que nous stockons sous forme hachée et jamais en clair. Votre pays, et si vous vous inscrivez comme créateur, comme entreprise ou comme agence. Un numéro de téléphone si vous choisissez d’en donner un\\u00A0: il est facultatif, et il sert à recevoir vos versements Mobile Money.",

      /* THE ONE-TIME CODE SENTENCES, AFTER THE EMAIL IDENTITY FLIP.

         THE IDENTIFIER CHANGED, AND THESE TWO PARAGRAPHS ARE WHERE THAT SHOWS.
         Registration, sign-in and both halves of password recovery now take an
         EMAIL ADDRESS (backend/app/modules/auth), users.phone is nullable and
         signup no longer asks for a number, and the one-time code is delivered
         to that address in French or English according to the account's
         country. collectAccount above and collectVerify below are written to
         that. Left alone they would have been false on the day the flip
         shipped, in the one document written to be read for exactly this fact.

         THE PHONE NUMBER IS STILL COLLECTED, and collectAccount still says so:
         it is optional now, and what it is for is a Mobile Money payout. The
         sentence names that purpose rather than leaving the reader to guess
         why a marketplace wants their number.

         THE DELIVERY CLAUSE IS BACK IN collectVerify, because it is true
         again. An earlier draft said "one-time codes we send to your phone"
         while auth/otp.py shipped nothing but LoggingSender, and the claim was
         cut back to what was merely held. Codes are really sent now, so the
         sentence says so. Expiry, single use and the cost of a wrong guess
         were always real and are untouched (OtpChallenge, and the attempts
         counter added by migration a1c5e8b30f7d).

         legal.privacy.sharedSms STAYS DELETED, in both languages and in the
         PRIVACY_DOCUMENT list (pages/LegalPage.tsx). It named an SMS provider
         that never existed, and nothing in this change brings one back.

         WHAT IS STILL OPEN, and it is the thing to chase before a regulator
         does: IF the code leaves this system through a third-party email
         provider, that provider receives a user's email address and belongs
         in the who-else-sees-it list below and in PRIVACY_DOCUMENT, in the
         slot sharedSms used to occupy. That line is NOT written here because
         nobody has confirmed which transport auth/otp.py sends through, and
         guessing a recipient would be the same error, in the same document,
         as naming one that does not exist. Whoever knows owns writing it. */
      collectVerify: "**Pour vérifier que c’est bien vous.** Les codes à usage unique que nous envoyons à votre adresse e-mail. Ils expirent, ils ne fonctionnent qu’une fois, et un code erroné coûte une tentative.",

      collectPublish: "**Ce que vous publiez.** Votre profil\\u00A0: nom affiché, biographie, catégories, tarifs et offres, disponibilité, photo de profil et images de portfolio. C’est votre vitrine, et elle est visible par tout le monde, y compris par les personnes qui ne sont pas connectées. N’y mettez rien que vous ne voudriez pas rendre public.",
      collectSocial: "**Vos comptes de réseaux sociaux connectés.** La plateforme et le pseudonyme que vous connectez, ainsi que les chiffres d’audience que nous récupérons pour ce compte (nombre d’abonnés, taux d’engagement et composition de l’audience) que nous obtenons depuis l’API publique de la plateforme elle-même. Nous ne recevons pas le mot de passe de votre compte social et nous ne pouvons pas publier en votre nom.",
      collectDocs: "**Documents de vérification.** Si vous demandez à être vérifié, la pièce d’identité ou le document d’immatriculation que vous téléversez. Ces documents sont **chiffrés au repos** et ne sont visibles que par le personnel qui les examine.",
      collectMoney: "**L’argent.** Ce que vous commandez ou ce pour quoi vous êtes engagé, le montant, la devise, et l’état du séquestre (escrow) qui le retient. Si vous êtes payé\\u00A0: votre numéro mobile money, le réseau, et le nom du titulaire du compte. Nous vous réaffichons ce numéro masqué, et il est transmis à notre prestataire de paiement plutôt qu’à l’autre partie.",
      collectWork: "**Le travail en commun.** Les messages et les pièces jointes que vous échangez avec l’autre partie à un contrat, le travail que vous soumettez et, si quelque chose tourne mal, la réclamation et les preuves versées à un litige.",
      collectTech: "**Données techniques.** Les données de connexion que tout service web traite simplement pour fonctionner\\u00A0: adresse IP, type d’appareil et de navigateur, horodatages.",

      whyTitle: "Pourquoi nous les collectons",
      why: "Pour faire fonctionner votre compte et prouver qu’il est le vôtre. Pour permettre aux marques et aux créateurs de se trouver. Pour conserver l’argent en sécurité sous séquestre, puis le libérer ou le rembourser. Pour vérifier que les personnes sont bien celles qu’elles disent être, ce qui est tout l’objet d’une place de marché où des inconnus paient des inconnus. Pour résoudre les litiges. Pour respecter nos obligations légales et fiscales. Pour garder la plateforme libre de fraude et de faux comptes.",
      whyNoSale: "**Nous ne vendons pas vos données à caractère personnel et nous ne les utilisons pas à des fins publicitaires.**",

      sharedTitle: "Qui d’autre y a accès",
      sharedGateway: "**Notre prestataire de paiement, FedaPay**, reçoit ce qu’un paiement ou un versement exige\\u00A0: le montant, la devise, et les coordonnées du payeur ou du bénéficiaire. L’argent ne peut pas circuler sans cela.",
      sharedSocial: "**Les plateformes sociales** (YouTube, Meta, et les autres à mesure que nous les ajoutons) reçoivent une requête portant sur les données publiques du compte que vous avez connecté.",
      sharedAi: "**Anthropic**, si vous utilisez la fonction facultative «\\u00A0rédiger ma bio\\u00A0»\\u00A0: les éléments de profil que vous avez déjà publiés sont envoyés pour produire une suggestion. Vous choisissez de l’enregistrer ou non. N’utilisez pas cette fonction pour quoi que ce soit que vous ne voulez pas voir sortir de nos systèmes.",
      sharedHosting: "**Nos hébergeurs et fournisseurs d’infrastructure**, qui stockent et servent les données sur nos instructions.",
      sharedCounterparty: "**L’autre partie à un contrat**, qui voit votre profil public, ce que vous avez convenu, vos messages et le travail que vous soumettez. **Elle ne voit jamais votre numéro de versement, ni vos documents, ni votre mot de passe.**",
      sharedAuthorities: "**Les autorités**, lorsque la loi l’exige.",

      whereTitle: "Où elles sont conservées",
      where: "Sur des serveurs que nous exploitons et sur l’infrastructure de nos prestataires, qui peuvent se trouver hors de votre pays. Les données de paiement et de versement sont traitées par FedaPay dans les marchés qu’il dessert.",

      retentionTitle: "Combien de temps nous les conservons",
      retention: "Tant que votre compte est ouvert, puis aussi longtemps que nous le devons\\u00A0: les enregistrements des transactions terminées, les documents fiscaux et les dossiers de litige doivent survivre au compte auquel ils se rattachent. Nous ne publions pas encore de calendrier de durées de conservation\\u00A0; lorsque nous en fixerons un, il figurera ici.",

      rightsTitle: "Vos choix et vos droits",
      rightsEdit: "Vous pouvez modifier ou supprimer la plus grande partie de votre profil depuis l’application à tout moment. Selon le lieu où vous vivez, vous pouvez disposer d’un droit d’accès, de rectification et d’effacement des données que nous détenons sur vous, du droit de vous opposer à l’usage que nous en faisons, ou d’en recevoir une copie. **Vous pouvez fermer votre compte vous-même, dans les paramètres de votre compte, sur le site web Kolabo.** Nous vous demandons alors votre mot de passe\\u00A0: une session ouverte ne doit pas suffire, à elle seule, à supprimer un compte. **Un compte rattaché à un contrat ou à un séquestre ne peut pas être fermé de cette manière**, et le formulaire vous l’indiquera\\u00A0: l’autre partie à une collaboration en conserve sa propre trace, et nous n’effaçons pas l’historique des sommes qui ont circulé. Pour fermer un tel compte, ou pour formuler l’une des autres demandes ci-dessus, **écrivez-nous** à l’adresse ci-dessous et nous vous répondrons.",
      rightsLimits: "Certaines choses ne peuvent pas être supprimées sur demande\\u00A0: un paiement effectué, un litige tranché, et tout ce qu’une loi nous impose de conserver.",

      securityTitle: "Sécurité",
      security: "Les mots de passe sont hachés. Les documents de vérification sont chiffrés au repos. Les numéros de versement sont masqués dans l’application. L’accès aux documents et aux litiges est limité au personnel qui les examine. Aucun système n’est parfaitement sûr, et nous ne prétendons pas le contraire.",

      childrenTitle: "Mineurs",
      children: "Kolabo s’adresse aux personnes de 18 ans et plus. La plateforme n’est pas destinée aux enfants et nous ne collectons pas sciemment leurs données. Si vous pensez qu’un enfant possède un compte, dites-le-nous et nous le supprimerons.",

      changesTitle: "Modifications",
      changes: "Si cette politique change, la date d’entrée en vigueur ci-dessus change avec elle. Si nous devions commencer à collecter quelque chose de sensiblement nouveau, nous l’indiquerions ici avant de commencer.",

      contactTitle: "Nous contacter",
      contactAddress: "Mocktar Technologies, C 1357 Houeyiho, 07BP91, Cotonou, Benin",
      contactRegistration: "Informations d’immatriculation\\u00A0:",
      contactRegistrationLink: "mocktar.com/legal/entities"
    }
  },

  /* Dans le bandeau du bas, à côté du support, sur toutes les pages. Le
     libellé le plus court qui reste sans ambiguïté : la page elle-même
     porte le titre complet. */
  footer: {
    privacy: "Confidentialité"
  }
};

const en = {
  legal: {
    effective: "Effective {{date}}",

    privacy: {
      title: "Privacy Policy",

      intro: "Kolabo is operated by Mocktar Technologies. This policy explains what we collect when you use Kolabo, why, who else sees it, and what you can ask us to do about it. It covers the Kolabo website and mobile apps. It does not cover mocktar.com or our other products, which have their own policies.",

      whoTitle: "Who we are",
      who: "Mocktar Technologies, C 1357 Houeyiho, 07BP91, Cotonou, Benin. RCCM RB/COT/26 A 119654, IFU 1200900488800. Full registration details, including our United States entity, are published at:",
      whoLink: "mocktar.com/legal/entities",

      collectTitle: "What we collect",
      collectAccount: "**To create your account.** Your email address, which is how you sign in and the only identifier we require. A password, which we store hashed and never in readable form. Your country and whether you are joining as a creator, a business or an agency. A phone number if you choose to give one. It is optional, and it is where your Mobile Money payouts are sent.",

      /* Rewritten for the email identity flip, and sharedSms still deleted —
         see the note above the French collectVerify for what changed, why,
         and the one line a reviewer still has to chase. */
      collectVerify: "**To verify it is you.** One-time codes we send to your email address. They expire, they work once, and a wrong code costs an attempt.",

      collectPublish: "**What you publish.** Your profile: display name, bio, categories, prices and packages, availability, profile photo and portfolio images. This is your storefront and is visible to anyone, including people who are not signed in. Please do not put anything in it you would not want public.",
      collectSocial: "**Your connected social accounts.** The platform and handle you connect, and the audience figures we retrieve for it (follower counts, engagement rates and audience breakdowns) which we fetch from the platform's own public API. We do not receive your social account password and we cannot post on your behalf.",
      collectDocs: "**Verification documents.** If you ask to be verified, the identity or business registration document you upload. These are **encrypted at rest** and are visible only to the staff who review them.",
      collectMoney: "**Money.** What you order or are hired for, the amount, the currency, and the state of the escrow holding it. If you are paid out: your mobile money number, the network, and the account name. We show that number back to you masked, and it goes to our payment provider rather than to the other party.",
      collectWork: "**Working together.** Messages and attachments you exchange with the other party to a contract, work you submit, and, if something goes wrong, the claim and the evidence in a dispute.",
      collectTech: "**Technical.** The usual connection data any web service processes to work at all: IP address, device and browser type, timestamps.",

      whyTitle: "Why we collect it",
      why: "To run your account and prove it is yours. To let brands and creators find one another. To hold money safely in escrow and release or refund it. To verify that people are who they say they are, which is the point of a marketplace where strangers pay strangers. To resolve disputes. To meet legal and tax obligations. To keep the platform free of fraud and fake accounts.",
      whyNoSale: "**We do not sell your personal data, and we do not use it for advertising.**",

      sharedTitle: "Who else sees it",
      sharedGateway: "**Our payment provider, FedaPay**, receives what a payment or payout requires: amount, currency, and the payer's or recipient's details. Money cannot move without this.",
      sharedSocial: "**Social platforms** (YouTube, Meta and others as we add them) receive a request for the public data on a handle you connected.",
      sharedAi: "**Anthropic**, if you use the optional \"draft my bio\" feature: the profile facts you already published are sent to draft a suggestion. You choose whether to save it. Do not use the feature for anything you do not want to leave our systems.",
      sharedHosting: "**Our hosting and infrastructure providers**, which store and serve the data on our instructions.",
      sharedCounterparty: "**The other party to a contract**, who sees your public profile, what you have agreed, your messages and your submitted work. **They never see your payout number, your documents, or your password.**",
      sharedAuthorities: "**Authorities**, where the law requires it.",

      whereTitle: "Where it is held",
      where: "On servers we operate and on our providers' infrastructure, which may be outside your country. Payment and payout data is processed by FedaPay in the markets it serves.",

      retentionTitle: "How long we keep it",
      retention: "While your account is open, and afterwards for as long as we must: records of completed transactions, tax records and dispute records have to outlive the account they belong to. We do not yet publish a schedule of retention periods; when we set one it will appear here.",

      rightsTitle: "Your choices and rights",
      rightsEdit: "You can edit or delete most of your profile from the app at any time. Depending on where you live, you may have rights to access the data we hold on you, correct it, have it erased, object to how we use it, or receive a copy. **You can close your account yourself, in account settings on the Kolabo website.** We ask for your password when you do, because a signed-in session on its own should not be enough to erase an account. **An account that has any contract or any escrow cannot be closed that way**, and the form will say so: the other party to a collaboration keeps its own record of it, and we do not erase the trail of money that moved. To close an account like that, or to make any of the other requests above, **write to us** at the address below and we will answer.",
      rightsLimits: "Some things we cannot delete on request: a completed payment, a resolved dispute, and anything a law requires us to keep.",

      securityTitle: "Security",
      security: "Passwords are hashed. Verification documents are encrypted at rest. Payout numbers are masked in the app. Access to documents and disputes is limited to staff who review them. No system is perfectly secure, and we do not claim otherwise.",

      childrenTitle: "Children",
      children: "Kolabo is for people aged 18 and over. It is not for children, and we do not knowingly collect their data. If you believe a child has an account, tell us and we will remove it.",

      changesTitle: "Changes",
      changes: "If this policy changes, the effective date above changes with it. If we ever start collecting something materially new, we will say so here before we start.",

      contactTitle: "Contact",
      contactAddress: "Mocktar Technologies, C 1357 Houeyiho, 07BP91, Cotonou, Benin",
      contactRegistration: "Registration details:",
      contactRegistrationLink: "mocktar.com/legal/entities"
    }
  },

  footer: {
    privacy: "Privacy"
  }
};

i18n.addResourceBundle("fr", "translation", fr, true, true);
i18n.addResourceBundle("en", "translation", en, true, true);
