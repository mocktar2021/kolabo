import i18n from "../i18n";

/* Copy for the party-details form: the block that says who signs a contract.

   REGISTERED AT RUNTIME, like parityStrings.ts, paymentStrings.ts and
   packageStrings.ts, and for the reason those files give: src/strings.ts is
   60 KB and a forty-key group lands in it invisibly. The consequence is the
   thing to remember. Every screen that uses a key below must import this
   module FOR ITS SIDE EFFECT, or it renders the raw key at the reader.
   components/profile/PartyDetailsSection.tsx is the only importer today.

   THE TWO SENTENCES THAT MATTER are party.hint and party.openToAll, and they
   are why this copy is worth a file rather than a handful of labels inlined in
   the component.

   party.hint has to say two things and may not soften either. First, these
   details appear word for word on contracts generated AFTER they are saved,
   because the snapshot is taken at generation and editing this later does not
   touch a contract that already exists. Second, Kolabo does not verify them.
   The spec is explicit that nothing in the UI or the document may imply these
   were checked: the platform collects no identity documents at all, and a
   party block is self-declared contract content, exactly as it would be on
   paper. Copy that hedged that into "we may verify" would promise a guarantee
   the platform does not offer, to the one reader who most needs the truth.

   party.openToAll exists because ORDER CANNOT CARRY THIS. Registered company
   is offered first, since on the business side it is the commonest answer, and
   first in a list reads as expected unless something says otherwise. Per the
   founder, businesses on Kolabo are not limited to registered ones, so the
   sole trader branch must be as easy to complete as a company and must not
   read as a lesser option. So a sentence says it outright.

   party.typeLocked is the client half of the party_type_immutable refusal
   (lib/errorMessages.ts). The form does not know whether a contract has been
   generated against this profile, and nothing in the GET says so, so rather
   than invent an API field it warns BEFORE the fact and lets the refusal
   arrive with its own sentence if it does. Both name support as the next step,
   because retyping the form is not one.

   WHY legal_name HAS PER-TYPE LABELS. It is one field carrying three
   different things: a company's registered name, a natural person's own name,
   and an association's name. The component looks up
   party.f_legal_name_<type> and falls back to the generic label, so only the
   types that need an override carry one.

   Hints name LOCAL documents rather than generic ones. RCCM for a registration
   number, IFU or NIF for a tax identifier, SARL and SA and GIE for a legal
   form: a reader in Cotonou or Lome should recognise the paper being asked for
   from the hint rather than guess at it.

   French first, like the other bundles: three of the five launch markets are
   francophone. */

const fr = {
  party: {
    title: "Qui signe vos contrats",
    hint: "Ces informations apparaissent telles quelles sur chaque contrat généré après leur enregistrement. Kolabo ne les vérifie pas : la plateforme écrit ce que vous déclarez, comme sur un contrat papier.",
    openToAll: "Les trois réponses sont acceptées de la même façon. Une entreprise n'a pas besoin d'être immatriculée pour travailler sur Kolabo.",
    /* Dit avant qu'un contrat existe, parce que le formulaire ne sait pas s'il
       en existe déjà un. Si le serveur refuse, party_type_immutable arrive
       avec sa propre phrase et désigne le même interlocuteur. */
    typeLabel: "Vous contractez en tant que",
    typeLocked: "Ce choix décide des informations demandées ensuite. Il ne peut plus changer une fois qu'un contrat a été généré : si votre situation a changé, écrivez au support.",

    type_registered_company: "Société immatriculée",
    desc_registered_company: "Une société inscrite au registre du commerce.",
    type_sole_trader: "En mon nom propre",
    desc_sole_trader: "Vous exercez en votre nom, immatriculé ou non.",
    type_association: "Association ou ONG",
    desc_association: "Une association, une ONG ou un groupement déclaré.",

    f_legal_name: "Dénomination sociale",
    f_legal_name_sole_trader: "Nom et prénoms",
    f_legal_name_association: "Nom de l'association",
    f_legal_form: "Forme juridique",
    f_registration_number: "Numéro d'immatriculation",
    f_tax_identifier: "Identifiant fiscal",
    f_address: "Adresse",
    f_country: "Pays",
    f_representative_name: "Nom du signataire",
    f_representative_capacity: "Qualité du signataire",

    h_legal_name: "Le nom exact tel qu'il figure sur vos documents.",
    h_legal_name_sole_trader: "Vos nom et prénoms, tels qu'ils figurent sur vos pièces.",
    h_legal_form: "Par exemple SARL, SA, SAS ou GIE.",
    h_registration_number: "Par exemple le numéro RCCM.",
    h_tax_identifier: "Par exemple l'IFU ou le NIF.",
    h_address: "L'adresse qui figurera sur le contrat.",
    h_representative_name: "La personne qui signe au nom de l'entité.",
    h_representative_capacity: "Par exemple gérant, directrice générale, président.",

    optional: "facultatif",
    country_placeholder: "Choisissez un pays",
    none: "Rien n'est encore enregistré. Sans ces informations, aucun contrat ne peut être généré pour vous.",
    incomplete: "Complétez les champs ci-dessus pour pouvoir enregistrer.",
    save: "Enregistrer ces informations",
    saved: "Informations enregistrées.",
  },
};

const en = {
  party: {
    title: "Who signs your contracts",
    hint: "These details appear word for word on every contract generated after you save them. Kolabo does not verify them: the platform writes down what you state, just as a paper contract would.",
    openToAll: "All three answers are accepted the same way. A business does not have to be registered to work on Kolabo.",
    typeLabel: "You contract as",
    typeLocked: "This choice decides which details are asked next. It cannot change once a contract has been generated: if your situation has changed, write to support.",

    type_registered_company: "Registered company",
    desc_registered_company: "A company entered in the companies register.",
    type_sole_trader: "In my own name",
    desc_sole_trader: "You work in your own name, registered or not.",
    type_association: "Association or NGO",
    desc_association: "A declared association, NGO or group.",

    f_legal_name: "Registered name",
    f_legal_name_sole_trader: "Full name",
    f_legal_name_association: "Name of the association",
    f_legal_form: "Legal form",
    f_registration_number: "Registration number",
    f_tax_identifier: "Tax identifier",
    f_address: "Address",
    f_country: "Country",
    f_representative_name: "Name of the signatory",
    f_representative_capacity: "Capacity of the signatory",

    h_legal_name: "The exact name as it appears on your documents.",
    h_legal_name_sole_trader: "Your full name, as it appears on your papers.",
    h_legal_form: "For example SARL, SA, SAS or GIE.",
    h_registration_number: "For example the RCCM number.",
    h_tax_identifier: "For example the IFU or NIF number.",
    h_address: "The address that will appear on the contract.",
    h_representative_name: "The person who signs on behalf of the entity.",
    h_representative_capacity: "For example manager, managing director or chair.",

    optional: "optional",
    country_placeholder: "Choose a country",
    none: "Nothing is saved yet. Without these details, no contract can be generated for you.",
    incomplete: "Fill in the fields above to save.",
    save: "Save these details",
    saved: "Details saved.",
  },
};

i18n.addResourceBundle("fr", "translation", fr, true, true);
i18n.addResourceBundle("en", "translation", en, true, true);
