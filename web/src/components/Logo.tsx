/* Kolabo mark: two interlocking chevrons that read as a "K" and as two parties
   meeting at a node. Built as inline SVG so it stays crisp and uses the brand
   gradient without depending on an exported image. */
export function Logo({ size = 30, withWordmark = true }: { size?: number; withWordmark?: boolean }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
      <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <defs>
          <linearGradient id="kolaboMark" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
            <stop stopColor="#1F2A78" />
            <stop offset="1" stopColor="#12B3A6" />
          </linearGradient>
        </defs>
        <rect width="48" height="48" rx="12" fill="url(#kolaboMark)" />
        <path d="M18 13v22" stroke="#fff" strokeWidth="4" strokeLinecap="round" />
        <path d="M33 13 21 24l12 11" stroke="#fff" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="21" cy="24" r="3.4" fill="#F5A524" />
      </svg>
      {withWordmark && (
        <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: size * 0.62, color: "var(--ink)", letterSpacing: "-0.01em" }}>
          Kolabo
        </span>
      )}
    </span>
  );
}
