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
import "./lib/undoStrings";
import "./lib/navMenuStrings";
/* After marketingStrings, which owns the landing.* group this one adds the
   brand-facing brief section to: addResourceBundle deep-merges, so the new
   keys join that group rather than replacing it. */
import "./lib/boardStrings";
/* Same arrangement: this one adds nav.notifications to the nav.* group
   i18n.ts owns, so it has to come after it. */
import "./lib/notificationStrings";
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
