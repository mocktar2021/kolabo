/* A date field that reads the same in Cotonou and in Charlotte.

   WHY NOT <input type="date">. Chrome takes the order of the displayed date
   from the operating system's locale and documents that web authors cannot
   change it. On a machine set to the United States that renders a birthday as
   04/20/1998, and 04/12 against 12/04 is the failure that does not look like
   one: both are real days, so a field in the wrong order looks answered rather
   than wrong, and the wrong day is what gets saved. lib/days.ts carries the
   argument and the conversions in full.

   THE PAGE STILL SPEAKS ISO. `value` comes in as "1998-04-20" and `onChange`
   gives back "1998-04-20", exactly as the native control did, so a page using
   this swaps one element for another and keeps its state, its save body and
   its prefill untouched. The DD/MM/YYYY text is this component's own business
   and never leaves it.

   AN UNFINISHED OR IMPOSSIBLE ENTRY REPORTS AS EMPTY, which is the one
   behaviour worth stating plainly. Half a date is not a date, so while
   somebody is typing, the page holds "" and anything gating a button on the
   field stays gated (Onboarding's Continue does exactly this). The message
   under the field is what tells them why, and it appears only once there is
   enough typed to be wrong rather than merely incomplete: a field that calls
   you wrong after one keystroke is a field people learn to ignore.

   THE SLASHES ARE TYPED FOR THEM by formatAsTyped, so the only invalid
   entries still reachable are a short one and a day that does not exist, and
   a pasted 1998-04-20 or 20.04.1998 lands correctly rather than being
   refused for its separators. */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { formatAsTyped, fromIsoDay, toIsoDay } from "../lib/days";

export function DayInput({
  id,
  value,
  onChange
}: {
  id: string;
  value: string;
  onChange: (iso: string) => void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState(() => fromIsoDay(value));

  /* The page can change `value` without a keystroke: ProfileSetup fills it
     from GET /profiles/influencer once the request lands. Re-derive the text
     only when the incoming ISO is not the one already on screen, or every
     render would fight whatever is being typed.

     `text` is deliberately not a dependency: this effect exists to follow the
     page, and listening to its own output is the loop it would become. */
  useEffect(() => {
    if ((toIsoDay(text) ?? "") !== value) setText(fromIsoDay(value));
  }, [value]);

  const bad = text.length === 10 && toIsoDay(text) === null;

  return (
    <>
      <input
        id={id}
        className="input"
        type="text"
        inputMode="numeric"
        autoComplete="bday"
        maxLength={10}
        placeholder={t("profile.birthDateFormat")}
        value={text}
        onChange={(e) => {
          const next = formatAsTyped(e.target.value);
          setText(next);
          onChange(toIsoDay(next) ?? "");
        }}
      />
      {bad && (
        <div className="hint" style={{ color: "var(--danger)" }}>
          {t("profile.birthDateBad")}
        </div>
      )}
    </>
  );
}
