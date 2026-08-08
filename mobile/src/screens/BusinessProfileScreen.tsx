import { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../lib/api";
import { errorText } from "../lib/errorMessages";
import { useAuth } from "../lib/auth";
import { Banner, Card, Field, GhostButton, PrimaryButton, Screen, Subtitle, Title } from "../components/ui";
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
      <Title>{t("biz.title")}</Title>
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
    </Screen>
  );
}
