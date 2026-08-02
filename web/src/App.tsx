import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { getStoredRole, isBusinessLike } from "./lib/auth";
import { CartProvider } from "./lib/cart";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import VerifyOtp from "./pages/VerifyOtp";
import Dashboard from "./pages/Dashboard";
import ProfileSetup from "./pages/ProfileSetup";
import AccountPage from "./pages/Account";
import EarningsPage from "./pages/Earnings";
import PaymentsPage from "./pages/Payments";
import Discover from "./pages/Discover";
import CampaignNew from "./pages/CampaignNew";
import CampaignList from "./pages/CampaignList";
import CampaignDetailPage from "./pages/CampaignDetail";
import CartPage from "./pages/CartPage";
import MessagesPage from "./pages/Messages";
import MyInvitations from "./pages/MyInvitations";
import ContractsList from "./pages/ContractsList";
import ContractPage from "./pages/ContractPage";
import DisputesPage from "./pages/Disputes";
import DisputeDetailPage from "./pages/DisputeDetail";
import AdminDisputesPage from "./pages/AdminDisputes";
import PublicProfilePage from "./pages/PublicProfile";
import Onboarding from "./pages/Onboarding";
import MarketingPage from "./pages/MarketingPage";

/* Campaigns are a brand-side artifact. The API answers 403 ("Only businesses
   and agencies can create campaigns.") to a creator, so hiding the create
   button is not enough — a bookmark or a typed URL would still land on a form
   whose only possible outcome is an error. A creator's equivalent of a
   campaign is a package on their profile, so they go back to the dashboard.
   Agencies buy like businesses do, hence isBusinessLike rather than a
   comparison against "business".

   The cart is guarded by the same wrapper for the same reason: checking out
   runs the identical role check server-side, and a creator who typed /cart
   would be looking at a basket they can never order.

   /payments is the third: GET /payments/spend filters on business_user_id,
   and a creator is on no escrow as the buyer, so the endpoint answers them
   four empty maps. Their equivalent is /earnings, and the two are separate
   screens rather than one because A BUYER PAYS GROSS WHILE A CREATOR RECEIVES
   NET — the commission comes off the release, not the payment — and because
   refunds are a real line in a buyer's ledger and money that never arrived in
   a creator's. */
function BrandOnly({ children }: { children: ReactNode }) {
  if (!isBusinessLike(getStoredRole())) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

/* The mirror image of BrandOnly. Invitations flow to creators: a business
   sends them, it never receives one, so /campaigns/invitations/mine can only
   ever answer a business with an empty list. A business's equivalent view is
   the proposals on its own campaign — that is where the answers to its
   invitations actually arrive — so it goes back to the dashboard rather than
   sitting on a page that is empty by construction. Agencies buy the way
   businesses do, hence isBusinessLike.

   Earnings are guarded by the same wrapper for the same reason, and it is
   worth spelling out: GET /payments/earnings answers a business with empty
   totals and an empty list ON PURPOSE. What a buyer wants there is SPEND,
   which is a different question with the opposite sign — commission is not
   deducted from it, refunds belong in it, and "pending" means money already
   gone from their wallet rather than money coming into it. Answering both
   from one endpoint would make every field mean two things, so buyer-side
   spend has its own endpoint (GET /payments/spend) and its own screen at
   /payments. A business sent away from here has somewhere to go. */
function CreatorOnly({ children }: { children: ReactNode }) {
  if (isBusinessLike(getStoredRole())) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    /* The cart wraps the router rather than living on the cart page: the nav
       indicator has to read the count on every screen, and a basket that only
       existed while /cart was mounted would forget itself the moment the
       buyer went back to browsing profiles — which is the entire journey it
       exists to support. */
    <CartProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/verify" element={<VerifyOtp />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/profile" element={<ProfileSetup />} />
          {/* Neither wrapper, and deliberately. Every account signs in with a
              phone number, has a password, is notified about things and may
              want to leave; the two sides of the market differ in what they
              DO on Kolabo, not in what an account is. */}
          <Route path="/account" element={<AccountPage />} />
          <Route path="/earnings" element={<CreatorOnly><EarningsPage /></CreatorOnly>} />
          {/* The buyer's half of the same question. See BrandOnly above for
              why it is not the same route with a role branch inside it. */}
          <Route path="/payments" element={<BrandOnly><PaymentsPage /></BrandOnly>} />
          <Route path="/discover" element={<Discover />} />
          <Route path="/campaigns" element={<CampaignList />} />
          <Route path="/campaigns/new" element={<BrandOnly><CampaignNew /></BrandOnly>} />
          <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
          <Route path="/cart" element={<BrandOnly><CartPage /></BrandOnly>} />
          {/* Neither wrapper: a contract has two parties and the thread
              belongs to both of them, so there is no role for this route to
              ask about. The gate is the contract itself, and it is the
              server's — /messaging answers 403 to anybody without one. */}
          <Route path="/messages" element={<MessagesPage />} />
          <Route path="/invitations" element={<CreatorOnly><MyInvitations /></CreatorOnly>} />
          <Route path="/contracts" element={<ContractsList />} />
          <Route path="/contracts/:id" element={<ContractPage />} />
          {/* Neither wrapper, for the same reason as messages: a dispute is a
              claim on money held between two people and either of them may be
              the one making it. The gate is being a party to the escrow, and
              /payments answers 403 to anybody else. */}
          <Route path="/disputes" element={<DisputesPage />} />
          <Route path="/disputes/:id" element={<DisputeDetailPage />} />
          {/* Unguarded on purpose, and it is not an oversight. Admin is not a
              role in this app — there is no admin login and getStoredRole
              cannot answer for one — so there is nothing here to ask. The
              gate is the X-Admin-Id header the page sends, which the API
              checks; without it every request on this screen answers 401 and
              the page shows nothing. Replace both when real admin auth
              lands. */}
          <Route path="/admin/disputes" element={<AdminDisputesPage />} />
          <Route path="/u/:userId" element={<PublicProfilePage />} />
          <Route path="/for-brands" element={<MarketingPage titleKey="marketingPage.brandsTitle" bodyKey="marketingPage.brandsBody" />} />
          <Route path="/for-creators" element={<MarketingPage titleKey="marketingPage.creatorsTitle" bodyKey="marketingPage.creatorsBody" />} />
          <Route path="/pricing" element={<MarketingPage titleKey="marketingPage.pricingTitle" bodyKey="marketingPage.pricingBody" />} />
        </Routes>
      </BrowserRouter>
    </CartProvider>
  );
}
