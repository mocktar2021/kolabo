import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout } from "../components/Layout";
import { useAuth } from "../lib/auth";
import { errorText } from "../lib/errorMessages";
import { COUNTRIES } from "../lib/countries";
import {
  PARTY_FIELDS,
  PARTY_TYPES,
  getMyPartyDetails,
  partyBody,
  partyIsComplete,
  partyValues,
  saveMyPartyDetails
} from "../lib/party";
import type { PartyDetails, PartyType } from "../lib/types";

/* WHO YOU ARE ON A CONTRACT, captured once per user on its own screen.

   WHY A SCREEN AND NOT A SECTION OF THE PROFILE FORM. These fields are not
   profile fields: nothing here is shown to the market, none of it is part of a
   storefront, and the whole set is read exactly once, at contract generation,
   and then frozen onto the contract. Putting a registration number beside a
   bio and a rate card would also put it beside a Save button that publishes
   things, which is the wrong neighbourhood for an address. The profile links
   here through components/PartyDetailsCard.tsx.

   WHY ONCE PER USER AND NOT ONCE PER CONTRACT. A party states the same thing
   about itself on every contract it signs, so asking per contract would be
   asking somebody to retype their address for each collaboration, and the two
   copies would disagree within a month. The profile holds the CURRENT details
   and the contract holds a SNAPSHOT taken at generation: editing here changes
   nothing on a contract that already exists.

   NEITHER ROLE WRAPPER IN App.tsx, deliberately. A contract names two parties
   and both have to be identified on it, so there is no creator-only or
   brand-only form of this question. The generation gate refuses with
   contract_business_party_missing or contract_creator_party_missing according
   to which side is short, and either side can be the one that is.

   NOTHING ON THIS SCREEN IS VERIFIED AND NOTHING ON IT MAY LOOK VERIFIED.
   party.notVerified says so in an alert above the form rather than in a hint
   under a field, because somebody should read it before they type. There is no
   badge, no tick and no "confirmed" state anywhere below, and a future change
   that adds one would turn a self-declaration into a claim Kolabo has not
   made. See the note on PartyType in lib/types.ts. */
export default function PartyDetailsPage() {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();

  /* The block as the SERVER last stored it, which is not the same thing as the
     form's values: it is what decides whether this is a first visit, and it is
     replaced by the PUT's own response so the screen never shows a value the
     server has not confirmed it kept. */
  const [saved, setSaved] = useState<PartyDetails | null>(null);
  /* NULL MEANS UNANSWERED, and the fields stay hidden until it is not. See the
     header: there is no default party_type, because a default would both show
     the wrong fields and nominate a normal case. */
  const [type, setType] = useState<PartyType | null>(null);
  /* Flat, keyed by request field name, and deliberately NOT cleared when the
     first question changes: legal_name, address and country belong to all
     three branches, and retyping an address because somebody corrected their
     own form of business is the kind of thing that makes a form abandoned. */
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let live = true;
    getMyPartyDetails(token)
      .then((existing) => {
        /* Null for anybody who has never filled this in, which is most
           accounts: a first visit is an empty form and not an error. */
        if (!live || !existing) return;
        setSaved(existing);
        setType(existing.party_type);
        setValues(partyValues(existing));
      })
      .catch((e) => {
        if (live) setError(errorText(e, t));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [token, t]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  function setValue(name: string, next: string) {
    setValues((prev) => ({ ...prev, [name]: next }));
  }

  const complete = type !== null && partyIsComplete(type, values);
  const chosenCountry = values.country ?? "";
  /* A STORED CODE THE DROPLIST DOES NOT KNOW GETS ITS OWN OPTION rather than
     being discarded. lib/countries.ts holds the seven target markets, and a
     block written against a country outside them, or one the list has not
     caught up with, would otherwise be silently emptied by the first render of
     this select and then saved blank. The raw code is an ugly label; losing a
     value somebody typed is worse. */
  const countryOptions =
    chosenCountry === "" || COUNTRIES.some((c) => c.code === chosenCountry)
      ? COUNTRIES
      : [...COUNTRIES, { code: chosenCountry, name: chosenCountry }];

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!type || !partyIsComplete(type, values)) return;
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      /* partyBody sends the chosen branch's fields and nothing else, so a
         registration number typed before somebody switched to the sole_trader
         branch does not travel with the sole_trader block. */
      const stored = await saveMyPartyDetails(token, partyBody(type, values));
      /* The response is the block as it now stands, including the display_label
         the server derived, so the screen takes it rather than refetching or
         keeping what was typed. A form still showing a field the server did
         not store is a form somebody presses save on twice. */
      setSaved(stored);
      setType(stored.party_type);
      setValues(partyValues(stored));
      setDone(true);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Layout>
      <div className="container page" style={{ maxWidth: 640 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <h1 style={{ margin: 0 }}>{t("party.title")}</h1>
          {/* A leaf screen, like the payout form: the way back belongs on it. */}
          <Link className="btn btn-ghost" to="/profile">{t("party.backToProfile")}</Link>
        </div>
        <p className="muted">{t("party.sub")}</p>

        {/* Before the form, not after it. */}
        <div className="alert alert-info">{t("party.notVerified")}</div>

        {error && <div className="alert alert-error">{error}</div>}
        {done && <div className="alert alert-success">{t("party.saved")}</div>}

        {loading ? (
          <p className="muted">{t("discover.loading")}</p>
        ) : (
          <>
            {/* Says what is missing and what it costs, once, and only while it
                is true. Not an error: nobody has done anything wrong by
                arriving here for the first time. */}
            {!saved && (
              <p className="muted" style={{ fontSize: 13.5 }}>{t("party.missing")}</p>
            )}
            <div className="card">
              <form onSubmit={onSubmit}>
                <div className="field">
                  <span className="label">{t("party.typeQuestion")}</span>
                  {/* THE THREE OPTIONS GET IDENTICAL TREATMENT, and that is
                      load-bearing rather than tidy. Same control, same weight,
                      a description each, no ordering cue and no option marked
                      as the usual one. */}
                  <div style={{ display: "grid", gap: 10, marginTop: 4 }}>
                    {PARTY_TYPES.map((option) => (
                      <label key={option} style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: "pointer" }}>
                        <input
                          type="radio"
                          name="party-type"
                          value={option}
                          checked={type === option}
                          disabled={busy}
                          style={{ marginTop: 3 }}
                          onChange={() => setType(option)}
                        />
                        <span>
                          <span style={{ fontWeight: 600, fontSize: 14.5 }}>{t(`party.type_${option}`)}</span>
                          <span className="muted" style={{ display: "block", fontSize: 13 }}>
                            {t(`party.typeDesc_${option}`)}
                          </span>
                        </span>
                      </label>
                    ))}
                  </div>
                  <div className="hint">{t("party.equalForms")}</div>
                </div>

                {type !== null && (
                  <>
                    {/* The lock, said while it can still be acted on. See the
                        header for why it is not enforced in this client. */}
                    <p className="muted" style={{ fontSize: 13 }}>{t("party.typeLocked")}</p>

                    {/* THE FIELDS COME FROM PARTY_FIELDS, not from a branch
                        written out here three times. The same list is what
                        partyBody sends and what the contract page's block
                        iterates to decide which rows a stored block has, so a
                        field added to a branch appears in all three places in
                        one edit. */}
                    {PARTY_FIELDS[type].map((field) => (
                      <div className="field" key={field.name}>
                        <label className="label" htmlFor={`party-${field.name}`}>
                          {t(`party.${field.labelKey}`)}
                        </label>
                        {field.name === "country" ? (
                          <select
                            id="party-country"
                            className="select"
                            value={chosenCountry}
                            disabled={busy}
                            onChange={(e) => setValue("country", e.target.value)}
                          >
                            {/* The empty option stays selectable so the field
                                starts unanswered rather than defaulting to
                                whichever market happens to be first. */}
                            <option value="">{t("party.countryChoose")}</option>
                            {countryOptions.map((c) => (
                              <option key={c.code} value={c.code}>{c.name}</option>
                            ))}
                          </select>
                        ) : field.name === "address" ? (
                          /* A textarea, because an address has lines in it and
                             one free-text field is what the server stores: it
                             is printed on the contract as written. */
                          <textarea
                            id="party-address"
                            className="input"
                            rows={2}
                            value={values.address ?? ""}
                            disabled={busy}
                            onChange={(e) => setValue("address", e.target.value)}
                          />
                        ) : (
                          <input
                            id={`party-${field.name}`}
                            className="input"
                            value={values[field.name] ?? ""}
                            disabled={busy}
                            onChange={(e) => setValue(field.name, e.target.value)}
                          />
                        )}
                        {field.hintKey !== null && (
                          <div className="hint">{t(`party.${field.hintKey}`)}</div>
                        )}
                      </div>
                    ))}

                    <button className="btn btn-primary btn-lg" type="submit" disabled={busy || !complete}>
                      {busy ? t("auth.working") : t("party.save")}
                    </button>
                    {/* Shown beside the disabled button rather than discovered
                        as a 422: the server refuses an incomplete block with
                        party_details_invalid, and arriving at that after eight
                        fields is worse than being told now. */}
                    {!complete && <div className="hint">{t("party.incomplete")}</div>}
                  </>
                )}
              </form>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
