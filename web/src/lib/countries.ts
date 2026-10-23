/* THE MARKETS KOLABO SELLS IN, and the one list every country picker in the
   web app reads: register, login, onboarding, profile setup, discover, the
   brief board, targeting, the payout form and both contract party forms all
   import COUNTRIES from here.

   WHY FOUR, WHERE THERE USED TO BE SEVEN. These are the countries where the
   payment provider can actually move money, read off the FeexPay production
   dashboard on 23 October 2026, where each of them carries activated channels
   rather than merely appearing in a country list. Ghana, Cameroon and Nigeria
   were never payable: GHS, XAF and NGN sit outside the XOF area the gateway's
   BCEAO licence covers. They were carried here as "shown for onboarding
   readiness", which in practice offered a creator in Lagos a signup ending at
   a payout form that cannot pay them.

   CHANGING THIS FILE IS NOT ENOUGH ON ITS OWN. Three other places declare
   which countries exist and none derives from another: COUNTRY_CONFIG in
   backend/app/core/country_config.py, the country_configs table seeded in
   backend/app/modules/config/service.py, and whatever GET /payments/config
   reports to the payout form. A market has to be opened or closed in all
   four, and nothing fails loudly when one of them is missed. */
export const COUNTRIES = [
  { code: "BJ", name: "Benin" },
  { code: "TG", name: "Togo" },
  { code: "CI", name: "Cote d'Ivoire" },
  { code: "SN", name: "Senegal" }
];

/* Every code this app has ever offered, closed markets included. Read by
   splitLocation below and by nothing else, deliberately.

   A location is stored as one free-text "City, CC" string, so a profile
   created while Ghana was open holds "Accra, GH". If the parser only knew the
   open markets, that profile would stop parsing the day Ghana closed and the
   whole string would land in the city field, which the creator would then see
   as their city being "Accra, GH". Closing a market must not corrupt the
   profiles created while it was open. */
const KNOWN_COUNTRY_CODES = ["BJ", "TG", "CI", "GH", "SN", "CM", "NG"];

/* Major cities per country, feeding the city droplist in profile setup and
   onboarding. Deliberately not exhaustive: the picker always offers an
   "Other…" escape hatch back to free text, so a missing city never blocks a
   creator. Names keep their local accents.

   The closed markets keep their entries. They cost nothing, they are only
   reached through a country that is no longer selectable, and they are what
   makes reopening one a single-line change rather than a research task. */
export const CITIES: Record<string, string[]> = {
  BJ: ["Cotonou", "Porto-Novo", "Abomey-Calavi", "Parakou", "Bohicon", "Natitingou", "Ouidah", "Lokossa"],
  TG: ["Lomé", "Sokodé", "Kara", "Atakpamé", "Kpalimé", "Dapaong", "Tsévié", "Aného", "Bassar"],
  CI: ["Abidjan", "Yamoussoukro", "Bouaké", "Daloa", "San-Pédro", "Korhogo", "Man", "Gagnoa"],
  GH: ["Accra", "Kumasi", "Tamale", "Takoradi", "Cape Coast", "Tema", "Ho", "Sunyani", "Koforidua"],
  SN: ["Dakar", "Thiès", "Touba", "Saint-Louis", "Kaolack", "Ziguinchor", "Rufisque", "Mbour", "Diourbel"],
  CM: ["Douala", "Yaoundé", "Bafoussam", "Bamenda", "Garoua", "Maroua", "Ngaoundéré", "Buea", "Kumba"],
  NG: ["Lagos", "Abuja", "Kano", "Ibadan", "Port Harcourt", "Benin City", "Kaduna", "Enugu"]
};

/* The backend keeps `location` as one free-text string: a dedicated country
   column is not worth a migration for the pilot. The location picker therefore
   composes "City, CC" (e.g. "Cotonou, BJ") on save and splits it back apart on
   load. */
export function joinLocation(city: string, countryCode: string): string | null {
  const c = city.trim();
  if (c && countryCode) return `${c}, ${countryCode}`;
  return c || countryCode || null;
}

export function splitLocation(location: string | null | undefined): { city: string; country: string } {
  if (!location) return { city: "", country: "" };
  const i = location.lastIndexOf(",");
  if (i !== -1) {
    const code = location.slice(i + 1).trim();
    if (KNOWN_COUNTRY_CODES.includes(code)) {
      return { city: location.slice(0, i).trim(), country: code };
    }
  }
  // Unparseable legacy values land in the city field with no country selected.
  return { city: location.trim(), country: "" };
}
