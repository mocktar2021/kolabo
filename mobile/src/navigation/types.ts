import type { NativeStackScreenProps } from "@react-navigation/native-stack";

/* The signed-out stack. Register can be entered with a role preselected (e.g.
   from a future deep link); undefined means "no preselection". */
export type AuthStackParamList = {
  Login: undefined;
  Register: { role?: string } | undefined;
  VerifyOtp: { phone: string };
  ForgotPassword: undefined;
};

/* The signed-in tree. `Tabs` hosts the bottom-tab navigator (whose tab
   screens keep their old names — React Navigation resolves navigate("X")
   across nested navigators, so no call site changed when tabs arrived);
   everything else is a detail screen pushed above the tabs with a native
   header. All names stay in ONE param list so AppScreenProps keeps typing
   every screen, tab or stacked. */
export type AppStackParamList = {
  Tabs: undefined;
  More: undefined;
  Dashboard: undefined;
  CreatorProfile: undefined;
  Contracts: undefined;
  ContractDetail: { id: string };
  Earnings: undefined;
  DisputeDetail: { id: string };
  Board: undefined;
  BusinessProfile: undefined;
  Spend: undefined;
  Campaigns: undefined;
  CampaignNew: undefined;
  CampaignDetail: { id: string };
  Discover: undefined;
  CreatorPublic: { userId: string };
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
