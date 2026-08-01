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
import Discover from "./pages/Discover";
import CampaignNew from "./pages/CampaignNew";
import CampaignList from "./pages/CampaignList";
import CampaignDetailPage from "./pages/CampaignDetail";
import CartPage from "./pages/CartPage";
import MyInvitations from "./pages/MyInvitations";
import ContractsList from "./pages/ContractsList";
import ContractPage from "./pages/ContractPage";
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
   would be looking at a basket they can never order. */
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
   businesses do, hence isBusinessLike. */
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
          <Route path="/discover" element={<Discover />} />
          <Route path="/campaigns" element={<CampaignList />} />
          <Route path="/campaigns/new" element={<BrandOnly><CampaignNew /></BrandOnly>} />
          <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
          <Route path="/cart" element={<BrandOnly><CartPage /></BrandOnly>} />
          <Route path="/invitations" element={<CreatorOnly><MyInvitations /></CreatorOnly>} />
          <Route path="/contracts" element={<ContractsList />} />
          <Route path="/contracts/:id" element={<ContractPage />} />
          <Route path="/u/:userId" element={<PublicProfilePage />} />
          <Route path="/for-brands" element={<MarketingPage titleKey="marketingPage.brandsTitle" bodyKey="marketingPage.brandsBody" />} />
          <Route path="/for-creators" element={<MarketingPage titleKey="marketingPage.creatorsTitle" bodyKey="marketingPage.creatorsBody" />} />
          <Route path="/pricing" element={<MarketingPage titleKey="marketingPage.pricingTitle" bodyKey="marketingPage.pricingBody" />} />
        </Routes>
      </BrowserRouter>
    </CartProvider>
  );
}
