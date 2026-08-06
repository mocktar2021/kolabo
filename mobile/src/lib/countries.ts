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
