/* Design tokens, taken from web/src/styles/theme.css so the two clients read
   as one brand. Hex values are copied from the CSS custom properties; kept as
   a flat object because React Native has no cascade to inherit them from.

   THE BRAND IS INDIGO-FIRST. Web's primary button is deep indigo (#1f2a78)
   with teal as the secondary emphasis — an earlier version of this file had
   a wrong indigo (#4338ca, a stock hue that appears nowhere in the brand)
   and used teal as the primary, which is much of why the two clients did
   not read as the same product. */
export const colors = {
  // Brand
  indigo: "#1f2a78",
  indigo700: "#26318c",
  indigo600: "#3341ad",
  teal: "#12b3a6",
  teal600: "#0e9a8f",
  tealSoft: "#e7f7f5",
  amber: "#f5a524",
  terracotta: "#e2725b",

  // Neutrals
  ink: "#151824",
  muted: "#5b6472",
  line: "#e6e8ef",
  bg: "#fbfaf8",
  surface: "#f6f8fc",
  surface2: "#eef1f8",

  // Semantic
  success: "#17916b",
  danger: "#d64545",
  warning: "#e0a500",

  white: "#ffffff",
} as const;

export const radius = { sm: 8, md: 12, lg: 20, pill: 999 };

export const space = (n: number) => n * 4;

export const font = {
  h1: 26,
  h2: 20,
  body: 15,
  small: 13,
  tiny: 12,
} as const;

/* Font families, matching web's --font-display (Poppins) and --font-body
   (Inter). The names are the keys expo-font registers from the
   @expo-google-fonts packages; App.tsx loads them before the tree renders,
   so a style can use these unconditionally. */
export const family = {
  display: "Poppins_700Bold",
  displaySemi: "Poppins_600SemiBold",
  body: "Inter_400Regular",
  bodyMedium: "Inter_500Medium",
  bodySemi: "Inter_600SemiBold",
  bodyBold: "Inter_700Bold",
} as const;

/* Elevation, translating web's --shadow-sm/--shadow-md. iOS reads the shadow*
   keys, Android reads elevation; both are carried on one object so a card
   states its depth once. */
export const shadow = {
  sm: {
    shadowColor: "#151824",
    shadowOpacity: 0.08,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 2,
  },
  md: {
    shadowColor: "#151824",
    shadowOpacity: 0.1,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 5,
  },
} as const;
