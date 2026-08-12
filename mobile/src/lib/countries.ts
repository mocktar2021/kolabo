/* The seven target markets, mirrored from web/src/lib/countries.ts. The two
   pilot markets (Benin, Togo) are enabled in the backend country config; the
   rest are shown for onboarding readiness. The dial prefix is added here (the
   web list carries only code + name) because the phone field on mobile shows
   it as a hint next to a numeric keypad.

   Names are per-language — "Côte d'Ivoire", not "Cote d'Ivoire", in a French
   UI. `countryName(code, language)` is the one place that choice is made;
   every chip row goes through it. */
export type Country = { code: string; en: string; fr: string; dial: string };

export const COUNTRIES: Country[] = [
  { code: "BJ", en: "Benin", fr: "Bénin", dial: "+229" },
  { code: "TG", en: "Togo", fr: "Togo", dial: "+228" },
  { code: "CI", en: "Côte d'Ivoire", fr: "Côte d'Ivoire", dial: "+225" },
  { code: "GH", en: "Ghana", fr: "Ghana", dial: "+233" },
  { code: "SN", en: "Senegal", fr: "Sénégal", dial: "+221" },
  { code: "CM", en: "Cameroon", fr: "Cameroun", dial: "+237" },
  { code: "NG", en: "Nigeria", fr: "Nigéria", dial: "+234" },
];

export function countryName(codeOrCountry: string | Country, language: string): string {
  const c = typeof codeOrCountry === "string"
    ? COUNTRIES.find((x) => x.code === codeOrCountry)
    : codeOrCountry;
  if (!c) return typeof codeOrCountry === "string" ? codeOrCountry : "";
  return language.startsWith("fr") ? c.fr : c.en;
}

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
