/* THE PRIVACY POLICY AND THE TERMS OF SERVICE, in both languages.

   Its own bundle for the reason every other *Strings module has one — the
   40 KB i18n.ts stays about core app copy — and for one more that is specific
   to these two documents: they are legal undertakings that a lawyer has to
   read, correct and re-read, and a legal document is easier to hand over as
   one file than as a diff scattered through the app's copy.

   IT ALSO ADDS footer.privacy AND footer.terms to the footer.* group
   marketingStrings.ts owns. Same arrangement notificationStrings has with
   nav.* and socialStrings has with profile.*: addResourceBundle runs with
   deep=true and overwrite=true, and main.tsx imports this AFTER
   marketingStrings, so the two keys join that group rather than replacing
   it.

   NOTHING IN THE APP IMPORTS THIS MODULE. main.tsx imports it for the side
   effect and nothing else, which is why the document OUTLINES — which heading
   comes before which paragraph — live in pages/LegalPage.tsx rather than
   here. App.tsx imports that page, main.tsx imports "./App" on its first
   line, and an import chain from App.tsx into any *Strings module would
   evaluate that bundle before "./lib/marketingStrings" further down the file:
   exactly the ordering the paragraph above depends on.

   FRENCH TYPOGRAPHY, AND IT IS DIFFERENT FROM THE REST OF THE APP. The French
   below sets the curly apostrophe and a non-breaking space before : ; ? and !
   No other bundle here does — they all use the straight apostrophe and an
   ordinary space. The divergence is deliberate and confined to these two
   documents: they are what a regulator, an app-store reviewer and a lawyer
   read, and they are the one place in the product where French punctuation is
   worth the trouble. Do not normalise them away.

   THE TWENTY-TWO NON-BREAKING SPACES BELOW ARE REAL U+00A0 CHARACTERS, AND
   THEY ARE INVISIBLE. An editor, a diff and a code review draw one exactly like
   the ordinary space beside it, and nothing in the toolchain will tell you
   when one is lost: a space is not a type error, so tsc, vitest and the build
   all stay green over French punctuation that has quietly stopped being
   French. One round trip through a tool that normalises whitespace is enough
   to lose the lot — this file lost all of them exactly that way while
   being committed, and the only thing that noticed was a byte count. So if you
   edit these strings, check the result the way this change was checked — by
   hashing the file and counting U+00A0 — and not by eye. Fourteen of them
   are on /legal/privacy and eight on /legal/terms.

   THE REGISTRATION IDENTIFIERS AND THE POSTAL ADDRESS ARE THE SAME STRING IN
   BOTH LANGUAGES. RB/COT/26 A 119654 and 1200900488800 identify a company in
   a register; they are not words. The address is left unlocalised for the
   same reason and to match lib/countries.ts, which spells every country in
   English in both bundles.

   THERE IS STILL NO GOVERNING-LAW CLAUSE IN THE TERMS, AND THAT IS WHY THIS
   PAGE CANNOT GO LIVE YET. Which entity contracts with users — Mocktar
   Technologies in Benin, or Mocktar Technologies LLC in North Carolina — and
   under whose law, is an open founder decision. It is omitted rather than
   filled with a placeholder because the two failures are not symmetrical: a
   Terms page without the clause is incomplete, while a Terms page naming the
   wrong forum is a representation made to every user who accepted it. The
   privacy policy never depended on that answer and went live without it; this
   document does depend on it. See the note on TERMS_DOCUMENT in
   pages/LegalPage.tsx for exactly where the section goes.

   Every factual claim below was checked against the repo at main @ c447e4ad:
   phone as the login identity and email optional (auth/models.py::User),
   hashed passwords (User.password_hash), expiring single-use codes
   (OtpChallenge), images in the database (MediaAsset.data), audience figures
   from the platforms' own APIs (profiles/enrichment.py), AI-drafted bios
   (profiles/bio_ai.py), documents encrypted at rest
   (VerificationDocument.ciphertext), escrow and payouts
   (payments/gateway_models.py) and the masked payout number
   (payouts.py::_method_out). If any of those change, this file changes with
   them. Two claims did not survive that check a second time; see the note
   above collectVerify. A third was wrong in the OTHER direction — it denied
   the platform a feature it has — see the note on deletion below.

   THE TERMS' MONEY AND LIFECYCLE CLAIMS WERE RE-READ AGAINST main @ 9a015999
   rather than trusted, precisely because that first check had already been
   wrong three times. These hold: the commission is settings.commission_bps =
   1500 (core/config.py); an ordinary release charges it on the whole escrow,
   which is the whole amount the brand paid (service.py::_release); the creator
   receives the escrow minus that commission, so the gateway's fee reduces the
   platform's share and never theirs; a refund charges nothing at all
   (service.py::_refund); an escrow cannot be funded on an unsigned contract
   and work cannot be submitted against an unfunded one; auto-release runs only
   against an OPEN submission, after settings.review_window_days; either party
   may raise a dispute while the escrow is HELD, and the other side gets
   settings.dispute_response_hours to answer; and an admin's split is refused
   unless the two figures total the escrow EXACTLY
   (resolution.py::_checked_amounts). FOUR OTHER CLAIMS HAD DRIFTED and were
   rewritten — see the note above the French terms block.

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
      who: "Mocktar Technologies, C 1357 Houeyiho, 07BP91, Cotonou, Benin — RCCM RB/COT/26 A 119654, IFU 1200900488800. Les informations d’immatriculation complètes, y compris celles de notre entité aux États-Unis, sont publiées sur mocktar.com/legal/entities/.",

      collectTitle: "Ce que nous collectons",
      collectAccount: "**Pour créer votre compte.** Votre numéro de téléphone, qui vous sert à vous connecter et qui est le seul identifiant que nous exigeons. Un mot de passe, que nous stockons sous forme hachée et jamais en clair. Votre pays, et si vous vous inscrivez comme créateur, comme entreprise ou comme agence. Une adresse e-mail si vous choisissez d’en donner une : elle est facultative.",

      /* THE SMS SENTENCES, AND WHY THEY NO LONGER SAY WHAT THEY SAID.

         Two claims in the drafted policy described an SMS provider that does
         not exist. backend/app/modules/auth/otp.py declares Sender(Protocol)
         and ships exactly one implementation of it — LoggingSender, which
         writes the code to the application log. No provider is integrated, so
         NOBODY OUTSIDE THIS SYSTEM RECEIVES A PHONE NUMBER IN ORDER TO
         DELIVER A CODE, and neither sentence was true on the day the page was
         due to go live.

         REMOVED: legal.privacy.sharedSms, in both languages — "Our SMS
         provider receives your phone number in order to deliver a code" —
         together with its entry in the who-else-sees-it list in
         PRIVACY_DOCUMENT (pages/LegalPage.tsx), where it sat between
         sharedGateway and sharedSocial. A present-tense line in a list headed
         "who else sees it", naming a recipient that does not exist, is not
         cautious drafting: it is a false statement about where a user's phone
         number goes, in the one document a regulator reads for exactly that.

         REWORDED: collectVerify, immediately below. "One-time codes we send
         to your phone" was untrue for the same reason, and it is in any case
         a claim about a delivery channel rather than about data held. It now
         says what is actually held — a code tied to your phone number — and
         the rest of the sentence is untouched, because expiry, single use and
         the cost of a wrong guess are all real (OtpChallenge, and the
         attempts counter added by migration a1c5e8b30f7d).

         BOTH SENTENCES BECOME TRUE AGAIN THE DAY AN SMS PROVIDER IS
         INTEGRATED, and whoever replaces LoggingSender in auth/otp.py owns
         restoring them: put sharedSms back in both languages and back into
         the PRIVACY_DOCUMENT list, and put the delivery clause back into
         collectVerify in both languages. Naming the provider in the policy is
         part of shipping it, not a follow-up. */
      collectVerify: "**Pour vérifier que c’est bien vous.** Les codes à usage unique rattachés à votre numéro de téléphone. Ils expirent, ils ne fonctionnent qu’une fois, et un code erroné coûte une tentative.",

      collectPublish: "**Ce que vous publiez.** Votre profil : nom affiché, biographie, catégories, tarifs et offres, disponibilité, photo de profil et images de portfolio. C’est votre vitrine, et elle est visible par tout le monde, y compris par les personnes qui ne sont pas connectées. N’y mettez rien que vous ne voudriez pas rendre public.",
      collectSocial: "**Vos comptes de réseaux sociaux connectés.** La plateforme et le pseudonyme que vous connectez, ainsi que les chiffres d’audience que nous récupérons pour ce compte — nombre d’abonnés, taux d’engagement et composition de l’audience — que nous obtenons depuis l’API publique de la plateforme elle-même. Nous ne recevons pas le mot de passe de votre compte social et nous ne pouvons pas publier en votre nom.",
      collectDocs: "**Documents de vérification.** Si vous demandez à être vérifié, la pièce d’identité ou le document d’immatriculation que vous téléversez. Ces documents sont **chiffrés au repos** et ne sont visibles que par le personnel qui les examine.",
      collectMoney: "**L’argent.** Ce que vous commandez ou ce pour quoi vous êtes engagé, le montant, la devise, et l’état du séquestre (escrow) qui le retient. Si vous êtes payé : votre numéro mobile money, le réseau, et le nom du titulaire du compte. Nous vous réaffichons ce numéro masqué, et il est transmis à notre prestataire de paiement plutôt qu’à l’autre partie.",
      collectWork: "**Le travail en commun.** Les messages et les pièces jointes que vous échangez avec l’autre partie à un contrat, le travail que vous soumettez et, si quelque chose tourne mal, la réclamation et les preuves versées à un litige.",
      collectTech: "**Données techniques.** Les données de connexion que tout service web traite simplement pour fonctionner : adresse IP, type d’appareil et de navigateur, horodatages.",

      whyTitle: "Pourquoi nous les collectons",
      why: "Pour faire fonctionner votre compte et prouver qu’il est le vôtre. Pour permettre aux marques et aux créateurs de se trouver. Pour conserver l’argent en sécurité sous séquestre, puis le libérer ou le rembourser. Pour vérifier que les personnes sont bien celles qu’elles disent être, ce qui est tout l’objet d’une place de marché où des inconnus paient des inconnus. Pour résoudre les litiges. Pour respecter nos obligations légales et fiscales. Pour garder la plateforme libre de fraude et de faux comptes.",
      whyNoSale: "**Nous ne vendons pas vos données à caractère personnel et nous ne les utilisons pas à des fins publicitaires.**",

      sharedTitle: "Qui d’autre y a accès",
      sharedGateway: "**Notre prestataire de paiement, FedaPay**, reçoit ce qu’un paiement ou un versement exige : le montant, la devise, et les coordonnées du payeur ou du bénéficiaire. L’argent ne peut pas circuler sans cela.",
      sharedSocial: "**Les plateformes sociales** (YouTube, Meta, et les autres à mesure que nous les ajoutons) reçoivent une requête portant sur les données publiques du compte que vous avez connecté.",
      sharedAi: "**Anthropic**, si vous utilisez la fonction facultative « rédiger ma bio » : les éléments de profil que vous avez déjà publiés sont envoyés pour produire une suggestion. Vous choisissez de l’enregistrer ou non. N’utilisez pas cette fonction pour quoi que ce soit que vous ne voulez pas voir sortir de nos systèmes.",
      sharedHosting: "**Nos hébergeurs et fournisseurs d’infrastructure**, qui stockent et servent les données sur nos instructions.",
      sharedCounterparty: "**L’autre partie à un contrat**, qui voit votre profil public, ce que vous avez convenu, vos messages et le travail que vous soumettez. **Elle ne voit jamais votre numéro de versement, ni vos documents, ni votre mot de passe.**",
      sharedAuthorities: "**Les autorités**, lorsque la loi l’exige.",

      whereTitle: "Où elles sont conservées",
      where: "Sur des serveurs que nous exploitons et sur l’infrastructure de nos prestataires, qui peuvent se trouver hors de votre pays. Les données de paiement et de versement sont traitées par FedaPay dans les marchés qu’il dessert.",

      retentionTitle: "Combien de temps nous les conservons",
      retention: "Tant que votre compte est ouvert, puis aussi longtemps que nous le devons : les enregistrements des transactions terminées, les documents fiscaux et les dossiers de litige doivent survivre au compte auquel ils se rattachent. Nous ne publions pas encore de calendrier de durées de conservation ; lorsque nous en fixerons un, il figurera ici.",

      rightsTitle: "Vos choix et vos droits",
      rightsEdit: "Vous pouvez modifier ou supprimer la plus grande partie de votre profil depuis l’application à tout moment. Selon le lieu où vous vivez, vous pouvez disposer d’un droit d’accès, de rectification et d’effacement des données que nous détenons sur vous, du droit de vous opposer à l’usage que nous en faisons, ou d’en recevoir une copie. **Vous pouvez fermer votre compte vous-même, dans les paramètres de votre compte, sur le site web Kolabo.** Nous vous demandons alors votre mot de passe : une session ouverte ne doit pas suffire, à elle seule, à supprimer un compte. **Un compte rattaché à un contrat ou à un séquestre ne peut pas être fermé de cette manière**, et le formulaire vous l’indiquera : l’autre partie à une collaboration en conserve sa propre trace, et nous n’effaçons pas l’historique des sommes qui ont circulé. Pour fermer un tel compte, ou pour formuler l’une des autres demandes ci-dessus, **écrivez-nous** à l’adresse ci-dessous et nous vous répondrons.",
      rightsLimits: "Certaines choses ne peuvent pas être supprimées sur demande : un paiement effectué, un litige tranché, et tout ce qu’une loi nous impose de conserver.",

      securityTitle: "Sécurité",
      security: "Les mots de passe sont hachés. Les documents de vérification sont chiffrés au repos. Les numéros de versement sont masqués dans l’application. L’accès aux documents et aux litiges est limité au personnel qui les examine. Aucun système n’est parfaitement sûr, et nous ne prétendons pas le contraire.",

      childrenTitle: "Mineurs",
      children: "Kolabo s’adresse aux personnes de 18 ans et plus. La plateforme n’est pas destinée aux enfants et nous ne collectons pas sciemment leurs données. Si vous pensez qu’un enfant possède un compte, dites-le-nous et nous le supprimerons.",

      changesTitle: "Modifications",
      changes: "Si cette politique change, la date d’entrée en vigueur ci-dessus change avec elle. Si nous devions commencer à collecter quelque chose de sensiblement nouveau, nous l’indiquerions ici avant de commencer.",

      contactTitle: "Nous contacter",
      contactAddress: "Mocktar Technologies, C 1357 Houeyiho, 07BP91, Cotonou, Benin",
      contactRegistration: "Informations d’immatriculation : mocktar.com/legal/entities/"
    },

    /* THE TERMS, AND THE FOUR SENTENCES THAT DID NOT SURVIVE A SECOND CHECK.

       The drafted Terms were verified against main @ c447e4ad. Three of that
       check's conclusions had already turned out to be wrong in the privacy
       policy (the two SMS sentences and the deletion one), so every money and
       lifecycle claim below was re-read against main @ 9a015999 rather than
       trusted. Four of them had drifted from the code:

       1. moneyHold listed three endings for a held escrow — accepted, review
          window expired, dispute decided. There is a FOURTH:
          payments/service.py::run_non_delivery_refunds. If nothing is ever
          submitted, both parties are warned at the creator's own quoted
          delivery date (contract.timeline_days) and the escrow is refunded to
          the brand settings.non_delivery_grace_days later. A brand reading the
          old list would think its money could sit held forever.

       2. moneyCommission said the commission is calculated on the full amount
          the brand pays. True of an ordinary release, where
          commission_for(escrow.amount) is exactly that — but NOT of a disputed
          split, where resolution.py charges commission_for(released) on the
          released part only. It now names the released amount and says that on
          a completed collaboration the two are the same number.

       3. disputes described the outcome as "the release or refund of the
          escrow", which is the binary model resolution.py was written to
          replace: "THE OUTCOME IS TWO FIGURES, NOT A VERDICT." An admin splits
          the escrow, either figure may be zero, and _checked_amounts refuses
          anything that does not total the escrow EXACTLY.

       4. ending said contracts and escrows "already running must finish
          first", which implies finishing them restores self-service closure.
          It does not. auth/service.py::delete_account queries Contract and
          Escrow with NO STATUS FILTER, so any contract or escrow that has ever
          existed blocks the endpoint permanently with 409
          auth_account_has_history. The block is not temporary and the text now
          says so — matching legal.privacy.rightsEdit, which already did.

       THERE IS STILL NO GOVERNING-LAW CLAUSE. See the note on TERMS_DOCUMENT
       in pages/LegalPage.tsx for where it goes and why it is omitted rather
       than guessed. */
    terms: {
      title: "Conditions générales d’utilisation",

      intro: "Les présentes conditions constituent un accord entre vous et Mocktar Technologies au sujet de votre utilisation de Kolabo.",

      whatTitle: "Ce qu’est Kolabo",
      what: "Une place de marché où des entreprises et des agences engagent des créateurs pour des collaborations rémunérées, et où l’argent de ce travail est conservé sous séquestre (escrow) jusqu’à ce que le travail soit livré et accepté. **Kolabo n’est pas partie à la collaboration elle-même.** L’accord d’exécution du travail lie la marque et le créateur ; nous fournissons la plateforme, nous conservons l’argent, et nous tranchons les litiges conformément aux présentes conditions.",

      whoTitle: "Qui peut l’utiliser",
      who: "Vous devez avoir 18 ans ou plus et être capable de contracter. Un seul compte par personne ou par entreprise. Vous êtes responsable de ce qui se passe sous votre compte : gardez donc votre mot de passe et vos codes à usage unique pour vous.",

      accountTitle: "Votre compte",
      account: "Inscrivez-vous avec des informations exactes et tenez-les à jour. Nous pouvons vous demander de vérifier votre identité ou l’immatriculation de votre entreprise, et nous pouvons suspendre un compte qui refuse de se vérifier, dont nous avons des motifs raisonnables de penser qu’il est frauduleux, ou qui sert à enfreindre les présentes conditions.",

      creatorsTitle: "Créateurs",
      creators: "Vous fixez vos tarifs, votre disponibilité et le travail que vous acceptez. Ce que vous publiez doit vous appartenir. Lorsque vous acceptez un contrat, vous vous engagez à livrer ce qu’il décrit, à la date qu’il indique. Il vous revient de signaler les partenariats rémunérés partout où la loi ou la plateforme sur laquelle vous publiez l’exige : cette obligation est la vôtre, pas la nôtre.",

      businessesTitle: "Entreprises",
      businesses: "Décrivez le travail avec exactitude, y compris tout ce qui pourrait changer la décision d’un créateur de l’accepter. Approvisionnez le séquestre avant le début du travail. Examinez rapidement le travail soumis ; à défaut, le séquestre se libère automatiquement à l’expiration du délai d’examen.",

      moneyTitle: "Argent, séquestre et commission",
      moneyFund: "La marque approvisionne un séquestre avant le début du travail.",
      moneyHold: "Nous conservons l’argent jusqu’à ce que le travail soit accepté, que le délai d’examen expire, ou qu’un litige soit tranché. **Si la date de livraison passe sans que rien n’ait été soumis**, nous vous avertissons tous les deux, puis nous remboursons la marque si rien n’arrive dans le délai indiqué.",
      moneyRelease: "À la libération, nous déduisons notre commission et versons le solde au créateur.",
      moneyCommission: "**Notre commission est calculée sur le montant libéré au créateur**, qui, pour une collaboration menée à son terme, correspond au montant total payé par la marque. Les frais de traitement du paiement sont prélevés sur notre part, pas sur celle du créateur.",
      moneyRefund: "Un remboursement rend l’argent à la marque. **Nous ne prélevons aucune commission sur les sommes remboursées.**",
      moneyPayout: "Les versements sont effectués sur le compte mobile money que vous enregistrez. Nous ne sommes pas responsables de l’argent envoyé à un numéro que vous avez saisi incorrectement.",
      moneyCurrency: "Les devises ne sont jamais mélangées. Une commande est libellée dans une seule devise.",

      offPlatformTitle: "Contourner la plateforme",
      offPlatform: "Le séquestre, la vérification et le règlement des litiges ne protègent que ceux qui les utilisent. Si vous sortez de Kolabo une collaboration que vous y avez trouvée afin d’échapper à la commission, vous perdez toute cette protection, et nous pouvons suspendre votre compte.",

      disputesTitle: "Litiges",
      disputes: "Chacune des parties peut ouvrir un litige tant que le séquestre est retenu ; son ouverture gèle les fonds. L’autre partie dispose d’un délai pour répondre, et la plupart des litiges s’arrêtent là. À défaut de réponse, ou si aucun accord n’est trouvé, nous tranchons. **Notre décision répartit le séquestre entre vous** — une part au créateur, le reste remboursé à la marque, les deux devant correspondre exactement à la somme retenue — et elle est définitive entre nous. Cela ne vous retire aucun droit de saisir un tribunal.",

      ownershipTitle: "Contenu et propriété",
      ownership: "Vous conservez la propriété de ce que vous créez et téléversez. Vous nous accordez la licence dont nous avons besoin pour l’afficher sur Kolabo et pour promouvoir la plateforme. Les droits sur le travail livré au titre d’un contrat se règlent entre la marque et le créateur, et devraient être écrits dans le contrat : Kolabo ne les tranche pas à votre place.",

      prohibitedTitle: "Ce qui est interdit",
      prohibited: "Les faux comptes, les abonnés achetés ou les chiffres d’audience fabriqués. L’identité ou les documents d’autrui. Le harcèlement, les discours haineux ou les contenus illégaux. Le paiement hors plateforme d’un travail trouvé sur celle-ci. Le scraping, le sondage ou l’attaque du service.",

      availabilityTitle: "Disponibilité",
      availability: "Kolabo est fourni en l’état. Nous ne promettons pas qu’il sera ininterrompu ni exempt d’erreurs, et les fonctionnalités évoluent.",

      liabilityTitle: "Notre responsabilité",
      liability: "Nous ne sommes pas responsables de la qualité, de la légalité ou de la ponctualité du travail convenu entre une marque et un créateur : nous ne sommes pas partie à cet accord. Dans la mesure permise par la loi, notre responsabilité envers vous au titre de Kolabo est limitée à la commission que nous avons perçue sur la transaction à laquelle se rapporte la réclamation. Rien ici ne limite une responsabilité qui ne peut pas légalement l’être.",

      endingTitle: "Y mettre fin",
      ending: "Vous pouvez fermer votre compte vous-même tant qu’aucun contrat et aucun séquestre ne s’y rattachent. **Dès qu’il en existe un, en cours ou terminé, la fermeture se demande auprès de nous** — l’autre partie conserve la trace de ce que vous avez convenu, et les sommes qui ont circulé ne sont pas effacées. Nous pouvons suspendre ou fermer un compte qui enfreint les présentes conditions, et nous libérerons toute somme régulièrement due.",

      changesTitle: "Modifications",
      changes: "Nous pouvons modifier les présentes conditions. Les modifications importantes seront notifiées dans l’application avant leur entrée en vigueur.",

      contactTitle: "Nous contacter",
      contactAddress: "Mocktar Technologies, C 1357 Houeyiho, 07BP91, Cotonou, Benin",
      contactRegistration: "Informations d’immatriculation : mocktar.com/legal/entities/"
    }
  },

  /* Dans le bandeau du bas, à côté du support, sur toutes les pages. Le
     libellé le plus court qui reste sans ambiguïté : la page elle-même
     porte le titre complet. */
  footer: {
    privacy: "Confidentialité",
    terms: "Conditions d’utilisation"
  }
};

const en = {
  legal: {
    effective: "Effective {{date}}",

    privacy: {
      title: "Privacy Policy",

      intro: "Kolabo is operated by Mocktar Technologies. This policy explains what we collect when you use Kolabo, why, who else sees it, and what you can ask us to do about it. It covers the Kolabo website and mobile apps. It does not cover mocktar.com or our other products, which have their own policies.",

      whoTitle: "Who we are",
      who: "Mocktar Technologies, C 1357 Houeyiho, 07BP91, Cotonou, Benin — RCCM RB/COT/26 A 119654, IFU 1200900488800. Full registration details, including our United States entity, are published at mocktar.com/legal/entities/.",

      collectTitle: "What we collect",
      collectAccount: "**To create your account.** Your phone number, which is how you sign in and the only identifier we require. A password, which we store hashed and never in readable form. Your country and whether you are joining as a creator, a business or an agency. An email address if you choose to give one — it is optional.",

      /* Reworded, and sharedSms deleted outright — see the note above the
         French collectVerify for what changed, why, and what has to be put
         back the day auth/otp.py grows a real Sender. */
      collectVerify: "**To verify it is you.** One-time codes tied to your phone number. They expire, they work once, and a wrong code costs an attempt.",

      collectPublish: "**What you publish.** Your profile: display name, bio, categories, prices and packages, availability, profile photo and portfolio images. This is your storefront and is visible to anyone, including people who are not signed in. Please do not put anything in it you would not want public.",
      collectSocial: "**Your connected social accounts.** The platform and handle you connect, and the audience figures we retrieve for it — follower counts, engagement rates and audience breakdowns — which we fetch from the platform's own public API. We do not receive your social account password and we cannot post on your behalf.",
      collectDocs: "**Verification documents.** If you ask to be verified, the identity or business registration document you upload. These are **encrypted at rest** and are visible only to the staff who review them.",
      collectMoney: "**Money.** What you order or are hired for, the amount, the currency, and the state of the escrow holding it. If you are paid out: your mobile money number, the network, and the account name. We show that number back to you masked, and it goes to our payment provider rather than to the other party.",
      collectWork: "**Working together.** Messages and attachments you exchange with the other party to a contract, work you submit, and — if something goes wrong — the claim and the evidence in a dispute.",
      collectTech: "**Technical.** The usual connection data any web service processes to work at all: IP address, device and browser type, timestamps.",

      whyTitle: "Why we collect it",
      why: "To run your account and prove it is yours. To let brands and creators find one another. To hold money safely in escrow and release or refund it. To verify that people are who they say they are, which is the point of a marketplace where strangers pay strangers. To resolve disputes. To meet legal and tax obligations. To keep the platform free of fraud and fake accounts.",
      whyNoSale: "**We do not sell your personal data, and we do not use it for advertising.**",

      sharedTitle: "Who else sees it",
      sharedGateway: "**Our payment provider, FedaPay**, receives what a payment or payout requires — amount, currency, and the payer's or recipient's details. Money cannot move without this.",
      sharedSocial: "**Social platforms** (YouTube, Meta and others as we add them) receive a request for the public data on a handle you connected.",
      sharedAi: "**Anthropic**, if you use the optional \"draft my bio\" feature: the profile facts you already published are sent to draft a suggestion. You choose whether to save it. Do not use the feature for anything you do not want to leave our systems.",
      sharedHosting: "**Our hosting and infrastructure providers**, which store and serve the data on our instructions.",
      sharedCounterparty: "**The other party to a contract**, who sees your public profile, what you have agreed, your messages and your submitted work. **They never see your payout number, your documents, or your password.**",
      sharedAuthorities: "**Authorities**, where the law requires it.",

      whereTitle: "Where it is held",
      where: "On servers we operate and on our providers' infrastructure, which may be outside your country. Payment and payout data is processed by FedaPay in the markets it serves.",

      retentionTitle: "How long we keep it",
      retention: "While your account is open, and afterwards for as long as we must — records of completed transactions, tax records and dispute records have to outlive the account they belong to. We do not yet publish a schedule of retention periods; when we set one it will appear here.",

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
      contactRegistration: "Registration details: mocktar.com/legal/entities/"
    },

    /* The same four corrections as the French block above; the long note is
       there. In short: moneyHold gained the non-delivery refund, moneyCommission
       now names the released amount rather than the amount paid, disputes
       describes a split rather than a binary verdict, and ending says the
       deletion block is permanent rather than temporary. */
    terms: {
      title: "Terms of Service",

      intro: "These terms are an agreement between you and Mocktar Technologies about your use of Kolabo.",

      whatTitle: "What Kolabo is",
      what: "A marketplace where businesses and agencies hire creators for paid collaborations, and where the money for that work is held in escrow until the work is delivered and accepted. **Kolabo is not a party to the collaboration itself.** The agreement to do the work is between the brand and the creator; we provide the platform, hold the money, and decide disputes according to these terms.",

      whoTitle: "Who may use it",
      who: "You must be 18 or over and able to enter a contract. One account per person or business. You are responsible for what happens under your account, so keep your password and your one-time codes to yourself.",

      accountTitle: "Your account",
      account: "Register with accurate information and keep it current. We may ask you to verify your identity or your business registration, and we may suspend an account that will not verify, that we reasonably believe is fraudulent, or that is being used to break these terms.",

      creatorsTitle: "Creators",
      creators: "You decide your prices, your availability and what work you take. What you publish must be yours to publish. When you accept a contract you agree to deliver what it describes, by the date it names. You are responsible for disclosing paid partnerships wherever the law or the platform you post on requires it — that obligation is yours, not ours.",

      businessesTitle: "Businesses",
      businesses: "Describe the work accurately, including anything that would change a creator's decision to take it. Fund the escrow before work begins. Review submitted work promptly; if you do not, the escrow releases automatically after the review window.",

      moneyTitle: "Money, escrow and commission",
      moneyFund: "The brand funds an escrow before work starts.",
      moneyHold: "We hold the money until the work is accepted, the review window expires, or a dispute is decided. **If the delivery date passes with nothing submitted at all**, we warn both of you, and refund the brand if nothing arrives within the time we give.",
      moneyRelease: "On release, we deduct our commission and pay the creator the balance.",
      moneyCommission: "**Our commission is calculated on the amount released to the creator**, which on a collaboration that runs to completion is the full amount the brand paid. Payment processing fees come out of our share, not the creator's.",
      moneyRefund: "A refund returns the money to the brand. **We take no commission on refunded money.**",
      moneyPayout: "Payouts go to the mobile money account you register. We are not responsible for money sent to a number you entered incorrectly.",
      moneyCurrency: "Currencies are never mixed. An order is in one currency.",

      offPlatformTitle: "Going around the platform",
      offPlatform: "Escrow, verification and dispute resolution only protect people who use them. If you take a collaboration you found on Kolabo off the platform to avoid commission, you lose all of that protection, and we may suspend your account.",

      disputesTitle: "Disputes",
      disputes: "Either party may open a dispute while the escrow is held; opening one freezes it. The other party has a window to respond, and most disputes end there. If they do not answer, or if the two of you do not agree, we decide. **Our decision splits the escrow between you** — a share to the creator and the rest back to the brand, and the two must add up to exactly what was held — and it is final as between us. That does not take away any right you have to go to court.",

      ownershipTitle: "Content and ownership",
      ownership: "You keep ownership of what you create and upload. You grant us the licence we need to display it on Kolabo and to promote the platform. Rights in the work delivered under a contract are between the brand and the creator, and should be written into the contract — Kolabo does not decide them for you.",

      prohibitedTitle: "What is not allowed",
      prohibited: "Fake accounts, bought followers or fabricated audience figures. Someone else's identity or documents. Harassment, hate speech or illegal content. Payment outside the platform for work found on it. Scraping, probing or attacking the service.",

      availabilityTitle: "Availability",
      availability: "Kolabo is provided as it is. We do not promise it will be uninterrupted or error-free, and features change.",

      liabilityTitle: "Our liability",
      liability: "We are not liable for the quality, legality or timeliness of work agreed between a brand and a creator — we are not a party to that agreement. To the extent the law allows, our liability to you in connection with Kolabo is limited to the commission we earned on the transaction the claim relates to. Nothing here limits liability that cannot lawfully be limited.",

      endingTitle: "Ending it",
      ending: "You can close your account yourself while no contract and no escrow is attached to it. **Once one exists — running or finished — closing the account is something you ask us to do**: the other party keeps their record of what you agreed, and money that has moved is not erased. We may suspend or close an account that breaks these terms, and will release any money properly owed.",

      changesTitle: "Changes",
      changes: "We may change these terms. Material changes will be notified in the app before they take effect.",

      contactTitle: "Contact",
      contactAddress: "Mocktar Technologies, C 1357 Houeyiho, 07BP91, Cotonou, Benin",
      contactRegistration: "Registration details: mocktar.com/legal/entities/"
    }
  },

  footer: {
    privacy: "Privacy",
    terms: "Terms"
  }
};

i18n.addResourceBundle("fr", "translation", fr, true, true);
i18n.addResourceBundle("en", "translation", en, true, true);
