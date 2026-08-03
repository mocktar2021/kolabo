/* Copy for the list-filter chips shared by the campaign, contract and
   invitation lists, registered as a resource bundle so the 40 KB i18n.ts
   stays focused on core app copy — the same arrangement filterStrings, the
   cart, the disputes queue and the money screens use.

   The chip labels for campaign and contract STATUSES are not here: those
   already have keys (campaign.status_*, contract.status_*) that the list rows
   render themselves, and the chips reuse them so a status is worded one way
   in one place. Only the values with no existing key live here — All, and the
   invitation states, which the invitation card until now printed raw (an
   English enum on a French screen). */
import i18n from "../i18n";

const fr = {
  all: "Tous",
  label: "Filtrer la liste",

  /* CampaignInvitation.status / the invitation as the creator reads it. The
     four values CampaignInvitation.status takes, worded for the person whose
     list it is: "Acceptée" is the one that became a contract, "Retirée" the
     one the brand took back before it was answered. */
  inv_invited: "En attente",
  inv_accepted: "Acceptée",
  inv_declined: "Refusée",
  inv_withdrawn: "Retirée"
};

const en = {
  all: "All",
  label: "Filter the list",

  inv_invited: "Pending",
  inv_accepted: "Accepted",
  inv_declined: "Declined",
  inv_withdrawn: "Withdrawn"
};

i18n.addResourceBundle("fr", "translation", { lf: fr }, true, true);
i18n.addResourceBundle("en", "translation", { lf: en }, true, true);
