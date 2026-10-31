import { describe, expect, it } from "vitest";
import {
  COLLECTION_NETWORK_LABELS,
  collectionNetworkLabel,
} from "./checkout";
import { PAYOUT_MODE_LABELS, payoutModeLabel } from "./checkout";

/* The collection picker's labels, and the one mistake worth pinning.

   This repo has no page tests, so this is a lib test about the data the
   funding screen renders from rather than about the screen. What it guards
   is the thing most likely to go wrong silently: the collection vocabulary
   and the payout vocabulary look almost identical, are not the same, and
   belong to two different legs of one provider. */

describe("collection network labels", () => {
  it("names every network the backend can offer in the four open markets", () => {
    /* Copied from feexpay._COLLECTION_NETWORKS, which took them verbatim
       from FeexPay's own validation error. A code with no label here renders
       as the raw code to a brand choosing a wallet, which is ugly rather
       than broken, but ugly in front of somebody paying money. */
    const offered = [
      "MTN", "MOOV", "CELTIIS BJ",
      "MOOV TG", "TOGOCOM TG",
      "MTN CI", "MOOV CI", "WAVE CI", "ORANGE CI",
      "WAVE SN", "ORANGE SN", "FREE SN",
    ];
    const missing = offered.filter((code) => !COLLECTION_NETWORK_LABELS[code]);
    expect(missing).toEqual([]);
  });

  it("falls back to the code rather than to an unpickable blank row", () => {
    /* A network added at the provider reaches this list before anybody adds
       a label. A dropdown row with no text cannot be chosen at all, which
       turns a cosmetic gap into a brand who cannot pay. */
    expect(collectionNetworkLabel("MPESA KE")).toBe("MPESA KE");
    expect(collectionNetworkLabel("")).toBe("");
  });

  it("is a separate map from the payout labels, with a different spelling", () => {
    /* THE TRAP. A payout to Cote d'Ivoire is keyed mtn_ci because that
       string goes in a URL path; a collection sends MTN CI in a field. One
       map serving both would have to carry both spellings of every operator
       and would return the wrong key the first time one of them changed. */
    expect(collectionNetworkLabel("MTN CI")).toBe("MTN Mobile Money");
    expect(payoutModeLabel("mtn_ci")).toBe("MTN Mobile Money");
    /* Neither map answers the other's key with a label. */
    expect(PAYOUT_MODE_LABELS["MTN CI"]).toBeUndefined();
    expect(COLLECTION_NETWORK_LABELS["mtn_ci"]).toBeUndefined();
  });

  it("gives the two Wave markets and the two Orange markets the same name", () => {
    /* Wave in Senegal and Wave in Cote d'Ivoire are one brand to a payer.
       The codes differ because the provider routes on them; the labels must
       not, or a brand reads two products where there is one. */
    expect(collectionNetworkLabel("WAVE CI")).toBe(collectionNetworkLabel("WAVE SN"));
    expect(collectionNetworkLabel("ORANGE CI")).toBe(collectionNetworkLabel("ORANGE SN"));
  });
});
