import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./lib/auth";
import "./i18n";
import "./lib/onboardingStrings";
import "./lib/marketingStrings";
import "./lib/cartStrings";
import "./lib/messagesStrings";
import "./lib/disputeStrings";
import "./lib/adminStrings";
import "./lib/accountStrings";
import "./styles/theme.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>
);
