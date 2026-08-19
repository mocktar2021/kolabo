import { useCallback, useEffect, useMemo, useState } from "react";
import { StyleSheet, Switch, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api";
import { errorText } from "../../lib/errorMessages";
import { SELLABLE_PLATFORMS, deliverableLabel, deliverablesFor } from "../../lib/platforms";
import { MIN_LIVE_PACKAGES, deactivationHidesProfile, minPrice } from "../../lib/pricing";
import type { Package, PackageInput, SocialAccount } from "../../lib/profileTypes";
import { Banner, ChoiceGroup, Field, GhostButton, Hint, PrimaryButton, SectionTitle, type Choice } from "../ui";
import { colors, family, font, radius, space } from "../../theme";
/* Side-effect import: registers profile.packageActive, packageInactive,
   packageDeactivateWarning and packageDeactivateConfirm on the i18n
   instance. Same arrangement the payment screens use for paymentStrings —
   see lib/packageStrings.ts for why the keys live outside strings.ts. */
import "../../lib/packageStrings";

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
  /* Which row is waiting on "turn it off anyway". Null the rest of the
     time. The switch stays controlled by p.is_active throughout, so a row
     never reads as off before the change has actually been saved. */
  const [confirmOffId, setConfirmOffId] = useState<string | null>(null);

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

  /* A failed fetch used to be recorded as new Set() — the same value as "no
     accounts connected" — which silently collapsed the platform picker to
     UGC-only on any transient error, with nothing on screen saying why. The
     failure now stays null ("unknown") and the picker offers everything the
     backend would accept, whose own validation remains the authority; a
     wrong guess costs one readable 400, a silent collapse costs a creator
     believing they cannot sell Instagram posts here. */
  const [socialsFailed, setSocialsFailed] = useState(false);
  useEffect(() => {
    setSocialsFailed(false);
    api<SocialAccount[]>(`/profiles/${userId}/social-accounts`, { token })
      .then((list) => setSocialPlatforms(new Set(list.map((a) => a.platform))))
      .catch(() => {
        setSocialPlatforms(null);
        setSocialsFailed(true);
      });
  }, [userId, token]);

  /* Sell only where the creator exists: platform options are the connected
     socials plus UGC (which is delivered to the brand, never posted). While
     the connected list is unknown — still loading, or failed — nothing is
     hidden, because hiding on ignorance looks exactly like a missing
     feature. */
  const platformOptions: Choice[] = useMemo(
    () =>
      SELLABLE_PLATFORMS.filter(
        (p) => p.id === "ugc" || socialPlatforms === null || socialPlatforms.has(p.id)
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

  /* What a buyer can currently order — the same figure onboarding-status
     reports as active_package_count, counted from the list already on screen
     so the warning below does not lag a round trip behind the switch that
     changes it. */
  const activeCount = packages.filter((p) => p.is_active).length;

  /* The switch. Turning a pack off is not deleting it: the row stays in this
     list, stays editable, and is orderable again the moment it goes back on.
     It only leaves the public page.

     Below MIN_LIVE_PACKAGES the creator leaves DISCOVERY as well, and nothing
     says so — the API does not refuse, the profile simply stops being
     returned by search. So the one gesture that crosses that line asks first.
     It asks rather than blocks: hiding a pack is a legitimate thing to want,
     and "turn it off anyway" is right there next to the sentence. */
  function askActive(pkg: Package, next: boolean) {
    if (!next && deactivationHidesProfile(activeCount)) {
      setConfirmOffId(pkg.id);
      return;
    }
    void setActive(pkg, next);
  }

  async function setActive(pkg: Package, next: boolean) {
    setConfirmOffId(null);
    setBusy(true);
    setError(null);
    try {
      /* PUT /packages/{id} takes a whole PackageIn rather than a patch, so
         every field travels as it stands with the one flag flipped: a key left
         out would be read as a cleared value, not as an unchanged one. */
      const body: PackageInput = {
        platform: pkg.platform,
        deliverable_type: pkg.deliverable_type,
        title: pkg.title,
        description: pkg.description,
        price_amount: pkg.price_amount,
        currency: pkg.currency,
        quantity: pkg.quantity,
        duration_value: pkg.duration_value,
        duration_unit: pkg.duration_unit,
        is_active: next,
      };
      const updated = await api<Package>(`/profiles/${userId}/packages/${pkg.id}`, {
        method: "PUT",
        token,
        body,
      });
      setPackages((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
      /* The go-live checklist upstairs counts active packages. Without this it
         would go on claiming the profile is live after the third one went
         off. */
      await onChanged();
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View>
      <SectionTitle>{t("profile.packagesTitle")}</SectionTitle>
      <Hint>{t("profile.packagesHint")}</Hint>
      {error ? <Banner kind="error">{error}</Banner> : null}

      {packages.length > 0 ? (
        <View style={{ gap: space(2), marginTop: space(2), marginBottom: space(3) }}>
          {packages.map((p) => (
            <View key={p.id}>
              <View style={[styles.row, !p.is_active && styles.rowOff]}>
                <View style={{ flexShrink: 1, opacity: p.is_active ? 1 : 0.6 }}>
                  <Text style={styles.rowTitle}>{p.title}</Text>
                  <Text style={styles.rowSub}>
                    {p.platform} · {deliverableLabel(p.deliverable_type)}
                    {p.quantity > 1 ? ` · ×${p.quantity}` : ""}
                  </Text>
                  {/* Named as well as greyed. A dimmed row on its own reads as
                      a rendering glitch; the word says which state it is in. */}
                  {!p.is_active ? <Text style={styles.offChip}>{t("profile.packageInactive")}</Text> : null}
                </View>
                <View style={{ flexDirection: "row", alignItems: "center", gap: space(2) }}>
                  <Text style={styles.price}>
                    {p.price_amount} {p.currency}
                  </Text>
                  <View style={{ alignItems: "center" }}>
                    <Text style={styles.switchLabel}>{t("profile.packageActive")}</Text>
                    <Switch
                      value={p.is_active}
                      onValueChange={(v) => askActive(p, v)}
                      disabled={busy}
                      accessibilityLabel={t("profile.packageActive")}
                      trackColor={{ false: colors.line, true: colors.teal }}
                    />
                  </View>
                  <Text style={styles.remove} onPress={() => remove(p.id)}>
                    {t("profile.remove")}
                  </Text>
                </View>
              </View>
              {/* Inline rather than an OS alert, the way AccountScreen asks
                  before deleting an account: the consequence stays on screen,
                  under the row it is about, until it is answered. */}
              {confirmOffId === p.id ? (
                <View style={{ marginTop: space(2) }}>
                  <Banner kind="info">
                    {t("profile.packageDeactivateWarning", { min: MIN_LIVE_PACKAGES })}
                  </Banner>
                  <View style={{ flexDirection: "row", gap: space(2) }}>
                    <View style={{ flex: 1 }}>
                      <GhostButton title={t("common.cancel")} onPress={() => setConfirmOffId(null)} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <PrimaryButton
                        title={t("profile.packageDeactivateConfirm")}
                        onPress={() => void setActive(p, false)}
                      />
                    </View>
                  </View>
                </View>
              ) : null}
            </View>
          ))}
        </View>
      ) : null}

      {socialPlatforms !== null && socialPlatforms.size === 0 ? (
        <Hint>{t("profile.connectSocialFirst")}</Hint>
      ) : null}
      {socialsFailed ? <Hint>{t("profile.socialsUnknown")}</Hint> : null}

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
  /* An inactive pack is paused, not gone: it keeps its place in the list and
     every control on it still works, but the field behind it goes grey. */
  rowOff: { backgroundColor: colors.surface2 },
  rowTitle: { fontSize: font.body, fontFamily: family.bodySemi, color: colors.ink },
  offChip: {
    alignSelf: "flex-start",
    marginTop: space(1),
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.sm,
    backgroundColor: colors.white,
    fontSize: font.tiny,
    fontFamily: family.bodySemi,
    color: colors.muted,
  },
  switchLabel: { fontSize: font.tiny, fontFamily: family.bodySemi, color: colors.muted, marginBottom: 2 },
  rowSub: { fontFamily: family.body, fontSize: font.tiny, color: colors.muted, marginTop: 2 },
  price: { fontSize: font.small, fontFamily: family.bodyBold, color: colors.ink },
  remove: { fontSize: font.small, color: colors.danger, fontFamily: family.bodySemi },
  fieldLabel: { fontSize: font.small, fontFamily: family.bodySemi, color: colors.ink, marginBottom: space(1.5) },
});
