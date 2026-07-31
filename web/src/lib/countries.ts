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
