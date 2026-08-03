/* Copy for the filter row shared by the earnings and spend screens,
   registered as a resource bundle so the 40 KB i18n.ts stays focused on the
   core app copy — the same arrangement the cart, the disputes queue, the
   admin console, the account settings and the two money screens use.

   The counterparty label is NOT here as one key: it is "Client" on the
   creator's screen and "Créateur" on the buyer's, because the counterparty is
   whoever is on the other side of the escrow. Each page passes its own, from
   its own bundle. */
import i18n from "../i18n";

const fr = {
  from: "Du",
  to: "Au",
  year: "Année",
  yearAll: "Toutes les années",
  campaign: "Campagne",
  campaignAll: "Toutes les campagnes",
  clear: "Effacer les filtres",

  /* Dit à l'écran dès qu'un filtre est actif. Des totaux qui ignorent le
     filtre posés à côté d'une liste filtrée, c'est exactement la façon dont
     quelqu'un additionne les lignes, trouve autre chose, et conclut que nos
     chiffres sont faux. */
  totals: "Totaux filtrés",
  totalsHint: "Les montants ci-dessus ne comptent que les lignes affichées.",

  none: "Aucune ligne ne correspond à ce filtre.",

  /* Affiché au-dessus du relevé quand une tuile est sélectionnée : le relevé
     ne montre plus que la catégorie choisie, dans sa devise. */
  showing: "Affiché : {{label}} · {{currency}}",
  showAll: "Tout afficher"
};

const en = {
  from: "From",
  to: "To",
  year: "Year",
  yearAll: "All years",
  campaign: "Campaign",
  campaignAll: "All campaigns",
  clear: "Clear filters",

  totals: "Filtered totals",
  totalsHint: "The figures above count only the rows shown.",

  none: "No line matches this filter.",

  showing: "Showing: {{label}} · {{currency}}",
  showAll: "Show all"
};

i18n.addResourceBundle("fr", "translation", { filt: fr }, true, true);
i18n.addResourceBundle("en", "translation", { filt: en }, true, true);
