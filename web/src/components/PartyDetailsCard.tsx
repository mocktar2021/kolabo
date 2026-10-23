import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import { getMyPartyDetails } from "../lib/party";

/* What the card knows about the block it is describing.

   "unknown" covers both the request in flight and the request having failed,
   and the two share a sentence on purpose: in neither case can the card
   honestly say whether the details are on file, and the neutral sentence is
   true in every state. Guessing "missing" while loading would show a call to
   action to somebody who has already answered it. */
type Known = "unknown" | "set" | "missing";

/* THE WAY INTO /profile/party, on the profile page where somebody manages the
   rest of what Kolabo holds about them.

   IT FETCHES FOR ITSELF, the way components/DeliverablesPanel.tsx does, rather
   than adding a third piece of state and a third effect to ProfileSetup.tsx.
   That is one more request on a screen that already makes two, and it buys the
   only thing worth having here: the card can say which state the reader is in.
   Without it the copy would have to be vague enough to be true either way, and
   "a contract cannot be generated while these are missing" is the entire
   reason to put a card on the profile rather than a line in a menu.

   A FAILED FETCH IS NOT AN ERROR HERE. It costs the distinction between two
   sentences, and the link still works: the form reads the same endpoint when
   it opens and will say the same thing with more room. Raising a banner on the
   profile over it would report somebody else's screen as broken.

   NOTHING ON THIS CARD IS A BADGE. The filled-in sentence says the fields are
   present. It does not say they were checked, because they were not: a party
   block is self-declared contract content and Kolabo verifies none of it. See
   the note on PartyType in lib/types.ts. */
export function PartyDetailsCard() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [known, setKnown] = useState<Known>("unknown");

  useEffect(() => {
    let live = true;
    getMyPartyDetails(token)
      .then((details) => {
        if (live) setKnown(details ? "set" : "missing");
      })
      .catch(() => {
        /* Deliberately swallowed. See the header. */
        if (live) setKnown("unknown");
      });
    return () => {
      live = false;
    };
  }, [token]);

  const body =
    known === "set" ? "party.cardBodySet" : known === "missing" ? "party.cardBodyMissing" : "party.cardBodyUnknown";

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>{t("party.cardTitle")}</h3>
      <p className="muted" style={{ fontSize: 13.5, marginTop: -4 }}>{t(body)}</p>
      <Link className="btn btn-ghost" to="/profile/party">
        {t(known === "set" ? "party.cardEdit" : "party.cardOpen")}
      </Link>
    </div>
  );
}
