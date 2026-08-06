import { useCallback, useEffect, useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { SELLABLE_PLATFORMS, deliverableLabel, deliverablesFor } from "../../lib/platforms";
import { minPrice } from "../../lib/pricing";
import type { Package, PackageInput, SocialAccount } from "../../lib/profileTypes";
import { Banner, ChoiceGroup, Field, Hint, PrimaryButton, SectionTitle, type Choice } from "../ui";
import { colors, font, radius, space } from "../../theme";

const CURRENCIES = ["XOF", "XAF", "GHS", "NGN"];
const UNIT_OPTIONS: Choice[] = [
  { value: "", label: "—" },
  { value: "seconds", label: "s" },
  { value: "minutes", label: "min" },
  { value: "hours", label: "h" },
];

const emptyForm = {
  platform: "ugc",
  deliverable_type: "ugc_video",
  title: "",
  price: "",
  currency: "XOF",
  quantity: "1",
  durationValue: "",
  durationUnit: "",
};

export function PackagesSection({
  userId,
  token,
  onChanged,
}: {
  userId: string;
  token: string | null;
  onChanged: () => void | Promise<void>;
}) {
  const { t } = useTranslation();
  const [packages, setPackages] = useState<Package[]>([]);
  const [socialPlatforms, setSocialPlatforms] = useState<Set<string> | null>(null);
  const [form, setForm] = useState({ ...emptyForm });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPackages(await api<Package[]>(`/profiles/${userId}/packages`, { token }));
    } catch {
      // handled by leaving the list as-is
    }
  }, [userId, token]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    api<SocialAccount[]>(`/profiles/${userId}/social-accounts`, { token })
      .then((list) => setSocialPlatforms(new Set(list.map((a) => a.platform))))
      .catch(() => setSocialPlatforms(new Set<string>()));
  }, [userId, token]);

  /* Sell only where the creator exists: platform options are the connected
     socials plus UGC (which is delivered to the brand, never posted). */
  const platformOptions: Choice[] = useMemo(
    () =>
      SELLABLE_PLATFORMS.filter(
        (p) => p.id === "ugc" || (socialPlatforms?.has(p.id) ?? false)
      ).map((p) => ({ value: p.id, label: p.label })),
    [socialPlatforms]
  );

  // Once socials load, snap the selected platform to a valid option.
  useEffect(() => {
    if (socialPlatforms === null) return;
    setForm((f) => {
      if (f.platform === "ugc" || socialPlatforms.has(f.platform)) return f;
      const first = SELLABLE_PLATFORMS.find((p) => p.id === "ugc" || socialPlatforms.has(p.id));
      return first ? { ...f, platform: first.id, deliverable_type: deliverablesFor(first.id)[0] ?? "" } : f;
    });
  }, [socialPlatforms]);

  const floor = minPrice(form.currency);
  const priceNum = Number(form.price);
  const belowFloor = form.price !== "" && priceNum < floor;
  const qty = Number(form.quantity);
  const qtyInvalid = !Number.isInteger(qty) || qty < 1 || qty > 100;
  const durationMismatch = (form.durationValue !== "") !== (form.durationUnit !== "");
  const canAdd = !!form.title.trim() && form.price !== "" && !belowFloor && !qtyInvalid && !durationMismatch;

  const deliverableOptions: Choice[] = deliverablesFor(form.platform).map((d) => ({
    value: d,
    label: deliverableLabel(d),
  }));

  async function add() {
    if (!canAdd) return;
    setBusy(true);
    setError(null);
    try {
      const body: PackageInput = {
        platform: form.platform,
        deliverable_type: form.deliverable_type,
        title: form.title.trim(),
        description: null,
        price_amount: priceNum,
        currency: form.currency,
        quantity: qty,
        duration_value: form.durationValue ? Number(form.durationValue) : null,
        duration_unit: form.durationUnit || null,
      };
      await api(`/profiles/${userId}/packages`, { method: "POST", token, body });
      setForm((f) => ({ ...emptyForm, platform: f.platform, deliverable_type: f.deliverable_type, currency: f.currency }));
      await load();
      await onChanged();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await api(`/profiles/${userId}/packages/${id}`, { method: "DELETE", token });
    } catch {
      // ignore; reload reflects true state
    }
    await load();
    await onChanged();
  }

  return (
    <View>
      <SectionTitle>{t("profile.packagesTitle")}</SectionTitle>
      <Hint>{t("profile.packagesHint")}</Hint>
      {error ? <Banner kind="error">{error}</Banner> : null}

      {packages.length > 0 ? (
        <View style={{ gap: space(2), marginTop: space(2), marginBottom: space(3) }}>
          {packages.map((p) => (
            <View key={p.id} style={styles.row}>
              <View style={{ flexShrink: 1 }}>
                <Text style={styles.rowTitle}>{p.title}</Text>
                <Text style={styles.rowSub}>
                  {p.platform} · {deliverableLabel(p.deliverable_type)}
                  {p.quantity > 1 ? ` · ×${p.quantity}` : ""}
                </Text>
              </View>
              <View style={{ flexDirection: "row", alignItems: "center", gap: space(2) }}>
                <Text style={styles.price}>
                  {p.price_amount} {p.currency}
                </Text>
                <Text style={styles.remove} onPress={() => remove(p.id)}>
                  {t("profile.remove")}
                </Text>
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {socialPlatforms !== null && socialPlatforms.size === 0 ? (
        <Hint>{t("profile.connectSocialFirst")}</Hint>
      ) : null}

      <Text style={styles.fieldLabel}>{t("profile.platform")}</Text>
      <ChoiceGroup
        options={platformOptions}
        value={form.platform}
        onChange={(v) => setForm({ ...form, platform: v, deliverable_type: deliverablesFor(v)[0] ?? "" })}
      />

      <View style={{ height: space(3) }} />
      <Text style={styles.fieldLabel}>{t("profile.deliverable")}</Text>
      <ChoiceGroup
        options={deliverableOptions}
        value={form.deliverable_type}
        onChange={(v) => setForm({ ...form, deliverable_type: v })}
      />

      <View style={{ height: space(3) }} />
      <Field
        label={t("profile.packageTitle")}
        value={form.title}
        onChangeText={(v) => setForm({ ...form, title: v })}
        maxLength={120}
      />

      <View style={{ flexDirection: "row", gap: space(2) }}>
        <View style={{ flex: 2 }}>
          <Field
            label={t("profile.price")}
            value={form.price}
            onChangeText={(v) => setForm({ ...form, price: v.replace(/\D/g, "") })}
            keyboardType="number-pad"
            placeholder="50000"
            hint={floor > 0 ? t("profile.minPrice", { n: floor, currency: form.currency }) : undefined}
          />
        </View>
        <View style={{ flex: 3 }}>
          <Text style={styles.fieldLabel}>{t("profile.currency")}</Text>
          <ChoiceGroup
            options={CURRENCIES.map((c) => ({ value: c, label: c }))}
            value={form.currency}
            onChange={(v) => setForm({ ...form, currency: v })}
          />
        </View>
      </View>
      {belowFloor ? <Hint>{t("profile.minPrice", { n: floor, currency: form.currency })}</Hint> : null}

      <View style={{ flexDirection: "row", gap: space(2), marginTop: space(2) }}>
        <View style={{ flex: 1 }}>
          <Field
            label={t("profile.quantity")}
            value={form.quantity}
            onChangeText={(v) => setForm({ ...form, quantity: v.replace(/\D/g, "") })}
            keyboardType="number-pad"
          />
        </View>
        <View style={{ flex: 1 }}>
          <Field
            label={t("profile.duration")}
            value={form.durationValue}
            onChangeText={(v) => setForm({ ...form, durationValue: v.replace(/\D/g, "") })}
            keyboardType="number-pad"
            placeholder="30"
          />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.fieldLabel}>{t("profile.durationUnit")}</Text>
          <ChoiceGroup
            options={UNIT_OPTIONS}
            value={form.durationUnit}
            onChange={(v) => setForm({ ...form, durationUnit: v })}
          />
        </View>
      </View>
      {durationMismatch ? <Hint>{t("profile.durationTogether")}</Hint> : null}

      <View style={{ height: space(3) }} />
      <PrimaryButton
        title={busy ? t("common.working") : t("profile.addPackage")}
        onPress={add}
        loading={busy}
        disabled={!canAdd}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    padding: space(3),
    gap: space(2),
  },
  rowTitle: { fontSize: font.body, fontWeight: "600", color: colors.ink },
  rowSub: { fontSize: font.tiny, color: colors.muted, marginTop: 2 },
  price: { fontSize: font.small, fontWeight: "700", color: colors.ink },
  remove: { fontSize: font.small, color: colors.danger, fontWeight: "600" },
  fieldLabel: { fontSize: font.small, fontWeight: "600", color: colors.ink, marginBottom: space(1.5) },
});
