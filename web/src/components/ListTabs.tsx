import { useTranslation } from "react-i18next";

/* Active / Completed, over a list the page already holds.

   WHY TABS AND NOT MORE CHIPS. The status chips underneath (ListFilter) and
   these answer different questions, and collapsing them into one row of
   chips would have made both worse. A tab is the LIFECYCLE question — is this
   still my problem, or is it history — and it is the one somebody asks first,
   every time they open the screen. The chips are the detail question inside
   whichever answer they picked. Different jobs, so different controls, and
   the tab sits above because it is asked first.

   THE COUNTS ARE THE POINT, not decoration. "Completed 12" is what tells a
   brand the shelf exists and is worth opening; an unlabelled second tab looks
   empty and gets ignored. A zero count is still shown, for the same reason —
   it teaches the split before there is anything on the other side.

   ALWAYS RENDERED, unlike ListFilter, which hides itself when there is
   nothing to choose between. Hiding this one would be worse than useless: a
   reader whose list is all active would never learn that finished work moves
   somewhere rather than vanishing, and would go looking for it in the wrong
   place the first time something completed. The caller still gates on the
   list being non-empty at all. */
export type Tab = "active" | "completed";

export function ListTabs({
  active,
  activeCount,
  completedCount,
  onChange
}: {
  active: Tab;
  activeCount: number;
  completedCount: number;
  onChange: (next: Tab) => void;
}) {
  const { t } = useTranslation();

  const tabs: { value: Tab; label: string; count: number }[] = [
    { value: "active", label: t("lf.tabActive"), count: activeCount },
    { value: "completed", label: t("lf.tabCompleted"), count: completedCount }
  ];

  return (
    <div
      role="tablist"
      aria-label={t("lf.tabsLabel")}
      style={{ display: "flex", gap: 18, marginTop: 16, borderBottom: "1px solid var(--line)" }}
    >
      {tabs.map((tab) => {
        const selected = tab.value === active;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.value)}
            style={{
              cursor: "pointer",
              background: "none",
              border: "none",
              /* The underline is on the button rather than a separate marker
                 so it cannot drift out of alignment with its label. */
              borderBottom: selected ? "2px solid var(--teal-600)" : "2px solid transparent",
              color: selected ? "var(--ink)" : "var(--muted)",
              fontWeight: selected ? 700 : 600,
              fontSize: 14.5,
              fontFamily: "var(--font-body)",
              padding: "6px 2px",
              marginBottom: -1
            }}
          >
            {tab.label}{" "}
            <span style={{ fontWeight: 600, color: "var(--muted)", fontSize: 13 }}>
              {tab.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
