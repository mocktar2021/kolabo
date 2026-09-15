import type { NavigatorScreenParams } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

/* The signed-out stack. Register can be entered with a role preselected (e.g.
   from a future deep link); undefined means "no preselection".

   Landing is the pre-auth ROOT — the carousel a fresh install opens on — and
   it is first here because it is first on screen. It is registered on every
   mount of this stack but is only the initial route the first time round; see
   lib/onboarding.ts and RootNavigator for what decides that. */
export type AuthStackParamList = {
  Landing: undefined;
  Login: undefined;
  Register: { role?: string } | undefined;
  VerifyOtp: { email: string };
  ForgotPassword: undefined;
};

/* The bottom tabs, as a param list of their own.

   EVERY NAME HERE IS ALSO IN AppStackParamList BELOW, and that is deliberate:
   screens stay typed with AppScreenProps wherever they happen to be mounted,
   so the shared list cannot lose them. This second list exists for one reason,
   which is to give navigate("Tabs", { screen: "Discover" }) a type.

   WHY THAT FORM IS NEEDED AT ALL. React Navigation resolves a route name
   UPWARDS: a tab screen's navigate("Cart") does not match a tab and bubbles
   out to the stack above, which is why every other navigation in this app is
   a bare name and works. CartScreen is the only screen that goes the other
   way, from a stack screen down into a tab. The stack router cannot handle a
   name outside its own routeNames, so a bare navigate("Discover") from there
   falls through to the mounted tab navigator: the tab really does change,
   underneath a Cart screen that stays on top, and the button reads as dead.
   Naming the host route and the tab inside it dispatches the action where it
   belongs.

   Both sides of the role fork are listed. RootNavigator mounts Discover and
   Campaigns for a brand and Board and Invitations for a creator, so which of
   these exist at runtime depends on who is signed in; the type covers the
   union, exactly as AppStackParamList always has. */
export type TabParamList = {
  Dashboard: undefined;
  Discover: undefined;
  Board: undefined;
  Campaigns: undefined;
  Invitations: undefined;
  Contracts: undefined;
  More: undefined;
};

/* The signed-in tree. `Tabs` hosts the bottom-tab navigator (whose tab
   screens keep their old names — React Navigation resolves navigate("X")
   across nested navigators, so no call site changed when tabs arrived);
   everything else is a detail screen pushed above the tabs with a native
   header. All names stay in ONE param list so AppScreenProps keeps typing
   every screen, tab or stacked. */
export type AppStackParamList = {
  /* `undefined` stays on the union so a bare navigate("Tabs") is still legal;
     NavigatorScreenParams is what types the { screen } form the cart uses. */
  Tabs: NavigatorScreenParams<TabParamList> | undefined;
  More: undefined;
  Dashboard: undefined;
  CreatorProfile: undefined;
  Contracts: undefined;
  ContractDetail: { id: string };
  /* Funding a contract, not a contract itself: the param is the contract to
     pay for, and the payment intent is created by the screen rather than
     passed in — a half-finished checkout must never be resumable from a stale
     navigation param. */
  Checkout: { contractId: string };
  Earnings: undefined;
  PayoutMethod: undefined;
  DisputeDetail: { id: string };
  Board: undefined;
  BusinessProfile: undefined;
  Spend: undefined;
  Campaigns: undefined;
  CampaignNew: undefined;
  CampaignDetail: { id: string };
  Discover: undefined;
  CreatorPublic: { userId: string };
  /* The basket. No param: the basket is client state (lib/cart.tsx), not
     something a route carries — a navigation param holding a list of packages
     would be a second copy of it, and the copy is the one that goes stale. */
  Cart: undefined;
  Invitations: undefined;
  Notifications: undefined;
  Messages: undefined;
  MessageThread: { userId: string; name: string };
  Disputes: undefined;
  Account: undefined;
};

export type AuthScreenProps<T extends keyof AuthStackParamList> = NativeStackScreenProps<
  AuthStackParamList,
  T
>;
export type AppScreenProps<T extends keyof AppStackParamList> = NativeStackScreenProps<
  AppStackParamList,
  T
>;
