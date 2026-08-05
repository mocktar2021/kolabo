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
/* And this one adds contract.status_cancelled / status_void to the contract.*
   group i18n.ts owns — the two statuses its block never got keys for. */
import "./lib/statusStrings";
/* The deliverables panel on the contract page. Owns the deliv.* group
   outright, so unlike the three above it has no ordering constraint against
   i18n.ts — it sits with the other feature bundles for the reason they all
   exist, which is to keep the 40 KB i18n.ts about core app copy. */
import "./lib/deliverableStrings";
/* What the API says when it refuses. Owns the apiError.* group outright, so
   no ordering constraint against i18n.ts either — but unlike every bundle
   above it belongs to no single feature: any page that calls the API can
   reach a sentence in it. See lib/errorMessages.ts. */
import "./lib/errorStrings";
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
