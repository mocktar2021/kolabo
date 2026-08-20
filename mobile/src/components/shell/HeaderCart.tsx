import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { Ionicons } from "@expo/vector-icons";
import { useCart } from "../../lib/cart";
import { colors, family, font } from "../../theme";

/* The basket, in the header of every tab a brand sees — the mobile stand-in
   for the web nav's cart link, in the place a phone reader expects it. It
   rides beside HeaderBell and is built the same way: headers render outside a
   screen, so the navigation object is handed in rather than taken from a hook.

   BRANDS ONLY, AND THAT IS THE WHOLE GUARD ON THIS SIDE. Mobile has no route
   guards; RootNavigator renders this only when isBusinessLike(role), which is
   the same rule the storefront's Add button runs under and the same rule the
   API applies (checkout answers 403 campaign_author_only to a creator).
   CartScreen says so in words for anyone who arrives some other way.

   The badge is the count of LINES, not of creators: a buyer who put four
   things in wants to see four, and how those four become orders is the cart
   screen's story to tell. It stays hidden while the keystore read is in
   flight rather than showing a zero the basket may not have. */
export function HeaderCart({ nav }: { nav: { navigate: (name: "Cart") => void } }) {
  const { t } = useTranslation();
  const { count, loading } = useCart();
  const showBadge = !loading && count > 0;

  return (
    <Pressable
      onPress={() => nav.navigate("Cart")}
      style={styles.wrap}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={t("cart.navAria", { n: count })}
    >
      <Ionicons name="cart-outline" size={24} color={colors.ink} />
      {showBadge ? (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{count}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  /* Tighter than the bell's 14 dp so the two together do not crowd a 360 dp
     header out of room for its title. */
  wrap: { paddingHorizontal: 10, paddingVertical: 4 },
  badge: {
    position: "absolute",
    top: 0,
    right: 2,
    minWidth: 17,
    height: 17,
    borderRadius: 9,
    backgroundColor: colors.teal600,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  badgeText: { color: colors.white, fontSize: font.tiny - 2, fontFamily: family.bodyBold },
});
