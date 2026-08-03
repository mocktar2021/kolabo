import { useTranslation } from "react-i18next";

/* A row of filter chips over a list the page already holds in memory.

   CLIENT-SIDE ON PURPOSE. The campaign, contract and invitation lists each
   fetch the whole set in one request and are short at pilot volume, so
   narrowing them is a filter of an array already on screen — no second
   request, no loading state, and the count never disagrees with what the eye
   can see. When a list outgrows that, the fix is a query param on its
   endpoint, not a rewrite of this component: it only ever renders the chips
   and reports which one is active.

   ONLY SHOWN WHEN IT HAS SOMETHING TO CHOOSE BETWEEN. A single-status list is
   a set of chips whose only outcome is the page somebody is already looking
   at — the same rule the money statement's filter row follows (hasOptions in
   lib/statement.ts). With fewer than two real options this renders nothing.

   "" IS ALL, everywhere: the empty value is the always-present first chip,
   and clicking the active chip again is not a toggle-off — All is how you
   clear, and it is always in reach. */
export type FilterOption = { value: string; label: string };

export function ListFilter({
  options,
  value,
  onChange
}: {
  /* The real choices, WITHOUT All — this component prepends it. Derive these
     from the values actually present in the list so no chip ever matches
     zero rows. */
  options: FilterOption[];
  /* "" means All. */
  value: string;
  onChange: (next: string) => void;
}) {
  const { t } = useTranslation();

  // One real option (or none) is nothing to filter; see the docstring.
  if (options.length < 2) return null;

  const chips: FilterOption[] = [{ value: "", label: t("lf.all") }, ...options];

  return (
    <div role="group" aria-label={t("lf.label")} style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
      {chips.map((chip) => {
        const active = chip.value === value;
        return (
          <button
            key={chip.value || "__all"}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(chip.value)}
            style={{
              cursor: "pointer",
              fontSize: 13,
              fontWeight: active ? 700 : 600,
              color: active ? "#fff" : "var(--muted)",
              background: active ? "var(--teal-600)" : "var(--surface-2)",
              border: "1px solid transparent",
              padding: "5px 12px",
              borderRadius: 999
            }}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
