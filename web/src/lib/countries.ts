/* The seven target markets. The two pilot markets (Benin, Togo) are enabled in
   the backend country config; the rest are shown for onboarding readiness. */
export const COUNTRIES = [
  { code: "BJ", name: "Benin" },
  { code: "TG", name: "Togo" },
  { code: "CI", name: "Cote d'Ivoire" },
  { code: "GH", name: "Ghana" },
  { code: "SN", name: "Senegal" },
  { code: "CM", name: "Cameroon" },
  { code: "NG", name: "Nigeria" }
];

/* Major cities per pilot country, feeding the city droplist in profile setup
   and onboarding. Deliberately not exhaustive: the picker always offers an
   "Other…" escape hatch back to free text, so a missing city never blocks a
   creator. Names keep their local accents. */
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
    if (COUNTRIES.some((c) => c.code === code)) {
      return { city: location.slice(0, i).trim(), country: code };
    }
  }
  // Unparseable legacy values land in the city field with no country selected.
  return { city: location.trim(), country: "" };
}
