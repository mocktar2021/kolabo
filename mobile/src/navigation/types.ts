import type { NativeStackScreenProps } from "@react-navigation/native-stack";

/* The signed-out stack. Register can be entered with a role preselected (e.g.
   from a future deep link); undefined means "no preselection". */
export type AuthStackParamList = {
  Login: undefined;
  Register: { role?: string } | undefined;
  VerifyOtp: { phone: string };
  ForgotPassword: undefined;
};

/* The signed-in stack. One screen for now; creator tabs land in the next
   slice, which is why this is already its own param list. */
export type AppStackParamList = {
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
};

export type AuthScreenProps<T extends keyof AuthStackParamList> = NativeStackScreenProps<
  AuthStackParamList,
  T
>;
export type AppScreenProps<T extends keyof AppStackParamList> = NativeStackScreenProps<
  AppStackParamList,
  T
>;
