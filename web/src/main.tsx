import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./lib/auth";
import { MeProvider } from "./lib/me";
import "./i18n";
import "./lib/onboardingStrings";
import "./lib/marketingStrings";
import "./lib/cartStrings";
import "./lib/messagesStrings";
import "./lib/disputeStrings";
import "./lib/adminStrings";
import "./lib/accountStrings";
import "./lib/earningsStrings";
import "./lib/spendStrings";
import "./lib/filterStrings";
import "./lib/listFilterStrings";
import "./lib/undoStrings";
import "./lib/navMenuStrings";
/* The catch-all page. Owns the notFound.* group outright, so it carries no
   ordering constraint, unlike the bundles further down that add keys into a
   group another file owns. */
import "./lib/notFoundStrings";
/* After marketingStrings, which owns the landing.* group this one adds the
   brand-facing brief section to: addResourceBundle deep-merges, so the new
   keys join that group rather than replacing it. */
import "./lib/boardStrings";
/* Same arrangement: this one adds nav.notifications to the nav.* group
   i18n.ts owns, so it has to come after it. */
import "./lib/notificationStrings";
/* And this one adds profile.noAudienceHint to the profile.* group i18n.ts
   owns, for the same reason and in the same way. */
import "./lib/socialStrings";
/* And this one adds the packages section's Active switch to that same
   profile.* group, so it carries the same ordering constraint. */
import "./lib/packageStrings";
/* And this one adds contract.status_cancelled / status_void to the contract.*
   group i18n.ts owns — the two statuses its block never got keys for. */
import "./lib/statusStrings";
/* And this one adds invitation.sent* to the invitation.* group i18n.ts owns:
   when each round of a negotiation was sent, for the thread the creator reads
   on their invitations page. Same ordering constraint, same reason. */
import "./lib/negotiationStrings";
/* And this one adds the reject control to the campaign.* group i18n.ts owns —
   the brand's answer that is a no, on the campaign page's proposal thread.
   Same ordering constraint, same reason. */
import "./lib/rejectionStrings";
/* The deliverables panel on the contract page. Owns the deliv.* group
   outright, so unlike the three above it has no ordering constraint against
   i18n.ts — it sits with the other feature bundles for the reason they all
   exist, which is to keep the 40 KB i18n.ts about core app copy. */
import "./lib/deliverableStrings";
/* The hosted checkout screen and the payout-method form. Owns the pay.* group
   outright, so no ordering constraint either. */
import "./lib/paymentStrings";
/* What the API says when it refuses. Owns the apiError.* group outright, so
   no ordering constraint against i18n.ts either — but unlike every bundle
   above it belongs to no single feature: any page that calls the API can
   reach a sentence in it. See lib/errorMessages.ts. */
import "./lib/errorStrings";
/* The privacy policy and the terms of service. Owns the legal.* group
   outright, but it ALSO adds footer.privacy and footer.terms to the footer.*
   group marketingStrings.ts owns — the two links the site footer has been
   waiting for — so it carries the same ordering constraint the three bundles
   above do, and for the same reason: it has to come after the file that owns
   the group.

   NOT LAST IN THIS LIST, whatever an older version of this comment claimed:
   googleStrings is imported below it. What is true is that this is the only
   bundle whose copy is a legal undertaking, and that reviewing it is a
   different job from reviewing the app's copy. */
import "./lib/legalStrings";
/* Signing in with Google. Joins TWO groups it does not own: auth.* belongs to
   i18n.ts and account.* belongs to accountStrings.ts, so it carries the same
   ordering constraint as the four bundles above and has to come after both of
   them. It is last of the bundles because it is the newest and because its
   copy is the only copy in this list that a signed-out stranger reads before
   anything else on the site. */
import "./lib/googleStrings";
import "./styles/theme.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AuthProvider>
      {/* Inside AuthProvider because it reads the token, and OUTSIDE the
          router (which App owns) because it must not remount on navigation —
          that is the difference between one /auth/me per session and one per
          page. */}
      <MeProvider>
        <App />
      </MeProvider>
    </AuthProvider>
  </React.StrictMode>
);
