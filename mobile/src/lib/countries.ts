/* The seven target markets, mirrored from web/src/lib/countries.ts. The two
   pilot markets (Benin, Togo) are enabled in the backend country config; the
   rest are shown for onboarding readiness. The dial prefix is added here (the
   web list carries only code + name) because the phone field on mobile shows
   it as a hint next to a numeric keypad. */
export type Country = { code: string; name: string; dial: string };

export const COUNTRIES: Country[] = [
  { code: "BJ", name: "Benin", dial: "+229" },
  { code: "TG", name: "Togo", dial: "+228" },
  { code: "CI", name: "Cote d'Ivoire", dial: "+225" },
  { code: "GH", name: "Ghana", dial: "+233" },
  { code: "SN", name: "Senegal", dial: "+221" },
  { code: "CM", name: "Cameroon", dial: "+237" },
  { code: "NG", name: "Nigeria", dial: "+234" },
];

export function dialFor(code: string): string {
  return COUNTRIES.find((c) => c.code === code)?.dial ?? "";
}

/* The backend keeps `location` as one free-text string ("City, CC", e.g.
   "Cotonou, BJ"). Mirror of joinLocation/splitLocation in web/src/lib/
   countries.ts: compose on save, split back on load. */
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
  return { city: location.trim(), country: "" };
}
