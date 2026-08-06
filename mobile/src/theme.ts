/* Design tokens, taken from web/src/styles/theme.css so the two clients read as
   one brand. Hex values are copied from the CSS custom properties; kept as a
   flat object because React Native has no cascade to inherit them from. */
export const colors = {
  teal: "#12b3a6",
  teal600: "#0e9a8f",
  tealSoft: "#e7f7f5",
  indigo: "#4338ca",
  ink: "#151824",
  muted: "#5b6472",
  line: "#e6e8ef",
  bg: "#fbfaf8",
  surface: "#f6f8fc",
  surface2: "#eef1f8",
  success: "#17916b",
  danger: "#d64545",
  white: "#ffffff",
} as const;

export const radius = { sm: 8, md: 12, lg: 16, pill: 999 };

export const space = (n: number) => n * 4;

export const font = {
  h1: 26,
  h2: 20,
  body: 15,
  small: 13,
  tiny: 12,
} as const;
