# Kolabo mobile — SDK 54 upgrade and test builds

## Why this upgrade happened

The app was on **Expo SDK 51**. Expo Go on the App Store and Play Store ships **SDK 54**, and Expo Go only runs the SDK it was built for — so the cheapest way to put the app in a tester's hands (install Expo Go, scan a QR code, free, both platforms) was closed to us.

It was also going to block iOS entirely. Apple enforces a minimum SDK for App Store and TestFlight submissions, and an SDK-51 build would very likely have been rejected — after paying for a developer account and waiting out enrolment.

**SDK 54 rather than 55 or 56, deliberately.** 54 is the newest version Expo Go supports today, and it is the **last release that supports the Legacy Architecture** — so if the New Architecture causes trouble we have a fallback. On 55+ there is no opt-out.

## What changed

| | Before | After |
|---|---|---|
| Expo SDK | 51 | **54.0.36** |
| React Native | 0.74.5 | **0.81.5** |
| React | 18.2.0 | **19.1.0** |
| React Navigation | 6.x | **7.x** |
| New Architecture | off | **on** |

Every Expo package version came from `expo@54.0.36`'s own `bundledNativeModules.json` — the same manifest `npx expo install --fix` resolves against — rather than being guessed. The resulting dependency graph was installed and resolved cleanly with no peer conflicts before this was committed.

**React Navigation had to go to 7.** `react-native-screens` 4.x is what SDK 54 pins, and Navigation 6 does not support it. This was not optional.

**The entry point did not change.** `expo/AppEntry.js` still exists in SDK 54, so `"main": "node_modules/expo/AppEntry.js"` stays as it was. Worth stating because it changed in some other SDK jumps and is the kind of thing people "fix" unnecessarily.

---

## ⚠️ What still has to be done locally

**This PR gets the versions and config right. It does not prove the app runs.** No install, build or type-check against the real source happened here — only dependency resolution. Before merging, someone must:

```bash
cd mobile
rm -rf node_modules package-lock.json
npm install
npx expo install --fix        # reconciles anything this PR missed
npx expo-doctor               # the real health check
npm run typecheck             # tsc --noEmit
npx expo start --clear
```

Expect to fix a handful of things. The likely candidates, in order:

1. **React Navigation 6 → 7 type and prop changes.** `NativeStackScreenProps` and the basic navigator APIs are unchanged, so most screens should compile untouched. Watch for removed options on `Tab.Navigator` and any use of `NavigationContainer`'s `independent` prop, which is gone.
2. **React 19.** `defaultProps` on function components and `PropTypes` are removed. Modern TSX rarely uses either.
3. **New Architecture.** The highest-risk item, because it is a runtime change rather than a compile-time one. If screens render blank or a native module misbehaves, set `"newArchEnabled": false` in `app.json`, rebuild, and confirm that was the cause before spending time elsewhere. SDK 54 is the last version where that escape hatch exists.

---

## ✅ The bundle identifier is settled: `com.kolaboafrica.app`

`app.json` sets both `ios.bundleIdentifier` and `android.package` to **`com.kolaboafrica.app`**. That is the final value, not a placeholder. It landed in PR #166 (KOL-68) and replaced `com.kolabo.app`, which derived from no domain anyone owns. Reverse DNS is meant to be a domain you control, and `kolaboafrica.com` is the canonical production domain.

**Do not change it again.** Neither store lets you alter the identifier on an app record that already exists. After the first submission, a different id is a different app: a new listing, with no installs, ratings or reviews carried across.

Two consequences are already in effect:

1. The APK installed under the old package is a **separate app** on the handset. The next build is an uninstall and a reinstall, not an update. Anyone still carrying a build from before PR #166 keeps it until they remove it by hand.
2. `scheme` stays `kolabo`, and it is not derived from the package name. `Linking.createURL()` in `src/screens/CheckoutScreen.tsx` builds the payment return link from `expo.scheme` alone, so changing the identifier does not touch the FedaPay return leg.

---

## Building for testers

### Android — available now

```bash
npm install -g eas-cli
eas login
eas build:configure          # links the project to your Expo account
eas build -p android --profile preview
```

The `preview` profile is `buildType: apk` **on purpose**. EAS defaults to `.aab`, which Google Play accepts and a human being cannot sideload. An APK is a file you send someone.

When it finishes, EAS gives you a download URL. Send that to testers; they enable "install from unknown sources" once and they're in. No store, no review, no Apple.

`EXPO_PUBLIC_API_URL` is set per profile in `eas.json`. Without it the app talks to `localhost:8000` and looks completely broken on a phone — this is the single most common "the build doesn't work" cause.

### iOS — needs an Apple Developer account

TestFlight and ad-hoc distribution both require **Apple Developer Program membership at $99/year**. There is no free route to an iOS device; the only free option is a simulator build on a Mac, which does not help a tester in Cotonou.

```bash
eas build -p ios --profile production
eas submit -p ios --latest      # to TestFlight
```

Note this uses `production`, not `preview` — on iOS the `preview` profile is `distribution: internal`, which means an ad-hoc build requiring every tester's device UDID registered up front. TestFlight avoids that.

**Start enrolment before you need it.** Individual enrolment is usually quick. Enrolling as an *organisation* needs a D-U-N-S number and identity verification and routinely takes one to three weeks. It is the longest-lead item in the mobile plan and it costs nothing to begin.

**→ See [`IOS_RELEASE.md`](./IOS_RELEASE.md)** for the full iOS path: enrolment choices, the permission and localisation config, the App Review items (demo accounts, privacy policy, the payments question), and the ordered checklist of what is blocked by what.

### Expo Go — fastest loop for you, not for testers

Now that we're on SDK 54:

```bash
cd mobile
EXPO_PUBLIC_API_URL=https://api.kolabo.mocktar.com npx expo start
```

Scan the QR with Expo Go. Good for tight iteration on your own device. Not good for testers: they need the right Expo Go version, a QR code, and your dev server running.

Note that deep links differ under Expo Go — it uses `exp://` rather than the `kolabo://` scheme. `Linking.createURL()` handles this, so the FedaPay payment return works in both, but if you are debugging the return leg specifically, test it in a real build too.

---

## The free tier

Expo's free plan includes a limited number of low-priority builds per month, reset monthly — enough for a pilot. Builds queue behind paying customers, so expect to wait. Starter is $19/month for build credit if the wait becomes tedious.

## CI

`.github/workflows/ci.yml` runs `npx tsc --noEmit` on `mobile/`. That will now type-check against React 19 and Navigation 7, so **the mobile CI job is the first real signal on this upgrade** — if it goes red, the fixes belong in this PR before merge.
