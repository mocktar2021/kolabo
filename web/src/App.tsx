import { BrowserRouter, Routes, Route } from "react-router-dom";
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
import MyInvitations from "./pages/MyInvitations";
import ContractsList from "./pages/ContractsList";
import ContractPage from "./pages/ContractPage";
import PublicProfilePage from "./pages/PublicProfile";
import Onboarding from "./pages/Onboarding";
import MarketingPage from "./pages/MarketingPage";

export default function App() {
  return (
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
        <Route path="/campaigns/new" element={<CampaignNew />} />
        <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
        <Route path="/invitations" element={<MyInvitations />} />
        <Route path="/contracts" element={<ContractsList />} />
        <Route path="/contracts/:id" element={<ContractPage />} />
        <Route path="/u/:userId" element={<PublicProfilePage />} />
        <Route path="/for-brands" element={<MarketingPage titleKey="marketingPage.brandsTitle" bodyKey="marketingPage.brandsBody" />} />
        <Route path="/for-creators" element={<MarketingPage titleKey="marketingPage.creatorsTitle" bodyKey="marketingPage.creatorsBody" />} />
        <Route path="/pricing" element={<MarketingPage titleKey="marketingPage.pricingTitle" bodyKey="marketingPage.pricingBody" />} />
      </Routes>
    </BrowserRouter>
  );
}
