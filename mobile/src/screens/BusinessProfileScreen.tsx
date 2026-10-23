import { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { PartyDetailsSection } from "../components/profile/PartyDetailsSection";
import { Banner, Card, Field, GhostButton, PrimaryButton, Screen, Subtitle } from "../components/ui";
import { space } from "../theme";
import type { AppScreenProps } from "../navigation/types";

type BusinessProfile = {
  user_id: string;
  company_name: string | null;
  industry: string | null;
  description: string | null;
};

export default function BusinessProfileScreen({ navigation }: AppScreenProps<"BusinessProfile">) {
  const { t } = useTranslation();
  const { userId, token } = useAuth();
  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    try {
      const p = await api<BusinessProfile>(`/profiles/business/${userId}`, { token });
      setCompanyName(p.company_name ?? "");
      setIndustry(p.industry ?? "");
      setDescription(p.description ?? "");
    } catch (e) {
      // 404 = no profile yet; a blank form is the right state.
      if (!(e instanceof ApiError && e.status === 404)) setError(errorText(e, t));
    }
  }, [userId, token, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    if (!userId || !companyName.trim()) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await api(`/profiles/business/${userId}`, {
        method: "PUT",
        token,
        body: {
          company_name: companyName.trim(),
          industry: industry.trim() || null,
          description: description.trim() || null,
        },
      });
      setSaved(true);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  if (!userId) return null;

  return (
    <Screen>
      <Subtitle>{t("biz.sub")}</Subtitle>
      <Card>
        {error ? <Banner kind="error">{error}</Banner> : null}
        {saved ? <Banner kind="success">{t("biz.saved")}</Banner> : null}
        <Field label={t("biz.companyName")} value={companyName} onChangeText={setCompanyName} />
        <Field
          label={t("biz.industry")}
          value={industry}
          onChangeText={setIndustry}
          placeholder={t("biz.industryPlaceholder")}
        />
        <Field
          label={t("biz.description")}
          value={description}
          onChangeText={setDescription}
          multiline
          numberOfLines={4}
          placeholder={t("biz.descriptionPlaceholder")}
        />
        <PrimaryButton
          title={busy ? t("common.working") : t("biz.save")}
          onPress={save}
          loading={busy}
          disabled={!companyName.trim()}
        />
      </Card>

      {/* A SEPARATE CARD, BELOW. company_name and the party block answer
          different questions and are saved to different endpoints.
          company_name is the trading name a buyer sees in search and on a
          contract card, and it is overwritten whole on every save. The party
          block is the legal entity that signs: it is snapshotted onto a
          contract at generation and frozen there, so editing it afterwards
          changes nothing about a contract that already exists. Merging the two
          into one form would invite somebody to fill a trading name and assume
          the entity was stated too.

          defaultType is registered_company because that is the commonest
          answer on this side. It is not a restriction: all three types are
          tappable here, which is what lets an unregistered trader or an NGO
          buy on Kolabo. */}
      <View style={{ height: space(4) }} />
      <Card>
        <PartyDetailsSection token={token} defaultType="registered_company" />
      </Card>
    </Screen>
  );
}
