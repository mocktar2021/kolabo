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

## Signing in with Google

The app ships the whole flow already: the button on the login and register
screens, the two questions a brand new Google address is asked, and the Google
confirmation the account screen accepts in place of a password.

**Corrected on 5 October. This section used to say the app ships no client id
"and that is deliberate". Both ids are committed**, in `app.json` under
`extra.googleWebClientId` and `extra.googleIosClientId`, and have been since the
clients were created. The sentence described the state before that and was
simply left behind.

**Two things are true now and neither is the old sentence.** With
`extra.googleWebClientId` empty the button does not render at all and an
`eas build` is never blocked on Google configuration, which is still the rule
and still worth keeping. And **iOS ignores both ids on purpose**:
`src/lib/config.ts` returns them empty when `Platform.OS === "ios"`, so Google
is absent from the iOS build whatever `app.json` says. That is an App Store
guideline 4.8 decision rather than a configuration one, it is explained at
length in that file, and `tests/googleOffOnIos.test.ts` pins it in both
directions. **Setting `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=""` in a build profile
is not a way to turn Google off anywhere**: an empty string is falsy and falls
through to the committed value. See KOL-116.

Three things have to be true before the button appears and works on a handset.

### 1. A development build, not Expo Go

Google sign in needs native code. Expo's Google authentication guide says of
both libraries it lists that they "can't be used in Expo Go because they
require custom native code", and this app uses
`@react-native-google-signin/google-signin`. So from the first build that
contains it, testing the button means an `eas build` (or a local prebuild), not
scanning a QR code into Expo Go. Everything else in the app still reloads over
the dev server as before, and Expo Go remains fine for any screen that is not
this one.

### 2. Three OAuth clients in Google Cloud Console

All three live in the **same** Google Cloud project, under APIs and services,
Credentials, Create credentials, OAuth client ID.

| Client type | What it needs | Where its id goes |
|---|---|---|
| **Web** | Already created for the browser app | `extra.googleWebClientId` in `app.json`, `VITE_GOOGLE_CLIENT_ID` for the web build, and the backend's `GOOGLE_CLIENT_IDS` |
| **Android** | Package name `com.kolaboafrica.app` plus the SHA-1 of the signing certificate | **Nowhere.** Android is matched by package name and signature, so no id from it is ever put in the bundle |
| **iOS** | Bundle ID `com.kolaboafrica.app` | `extra.googleIosClientId` in `app.json`, and its reversed form in the config plugin entry (see below) |

**The web client id is the one that matters most, and it is not obvious why.**
It is what the native library takes as `webClientId`, its *server* client id,
and it is what makes Google issue an ID token at all: without it the sign in
succeeds and the token comes back null. Google's own backend verification
guidance is to check the token's `aud` against this same web client id, which
is what `backend/app/modules/auth/google.py` does against `GOOGLE_CLIENT_IDS`.
So the web client id is already the right value in `GOOGLE_CLIENT_IDS` and
nothing has to be added there for mobile.

**Getting the Android SHA-1.** EAS holds the keystore, so ask it rather than
looking for a file:

```bash
cd mobile
eas credentials -p android
```

Pick the build profile, then the keystore, and read off the SHA-1 fingerprint.
Note the fingerprint is per signing certificate, so there can be more than one
to register: the EAS keystore used for the APKs testers install, and, once the
app is on Google Play with Play App Signing, the SHA-1 Play shows under Setup,
App integrity. Add every one of them to the Android OAuth client, or sign in
fails on whichever build was signed by the missing one. The symptom is
`DEVELOPER_ERROR`, which says nothing about certificates.

### 3. Fill in `app.json`, and add the plugin entry with the iOS client

Two of the three values go straight into `expo.extra`, which already has empty
slots for them:

```json
"extra": {
  "googleWebClientId": "<the WEB client id>.apps.googleusercontent.com",
  "googleIosClientId": "<the IOS client id>.apps.googleusercontent.com"
}
```

`EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` and `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`
override these at bundle time if a build ever needs to point somewhere else,
exactly as `EXPO_PUBLIC_API_URL` overrides `apiBaseUrl`.

**Corrected on 5 October: the config plugin entry is no longer missing.** It is
in `app.json` under `plugins`, with an `iosUrlScheme`, added when the iOS client
was created. What follows is why it could not be added earlier, kept because it
is still the reason the entry must never be present without a client behind it.

The library's plugin requires `iosUrlScheme` and throws when it is absent or
does not begin with `com.googleusercontent.apps`, which would fail
`expo prebuild` and therefore `eas build`. The value is the iOS client id
reversed, so it cannot be written down until that client exists. Android needs
none of this: the plugin does nothing for Android in the non Firebase path, and
the native module is autolinked by the dependency alone.

**The entry stays even though iOS no longer offers Google**, and that is a
deliberate call rather than an oversight. Guideline 4.8 is about what an app
offers a person, and the plugin only registers a URL scheme for a flow that
cannot start, so a dormant SDK offers nothing. Removing it needs an
`app.config.js` to vary `plugins` by platform, which is a build system change
rather than a code one. Revisit only if a reviewer raises it.

When the iOS client exists, add this to `expo.plugins` in `app.json`, beside
the `expo-image-picker` entry already there:

```json
[
  "@react-native-google-signin/google-signin",
  {
    "iosUrlScheme": "com.googleusercontent.apps.<the IOS client id, reversed>"
  }
]
```

The reversed form is the iOS client id with its two halves swapped: an id of
`123-abc.apps.googleusercontent.com` becomes
`com.googleusercontent.apps.123-abc`. Google Cloud Console shows it on the iOS
client as the **iOS URL scheme**, so copy it from there rather than assembling
it by hand.

### What happens if only some of this is done

| State | Behaviour |
|---|---|
| No ids at all | No button anywhere, on either platform. The app is exactly as it was |
| Web id set, no Android client in Google Cloud | Button appears, Android sign in fails with `DEVELOPER_ERROR` |
| Web id set, Android client registered | Android works. This is the pilot configuration |
| iOS id set but no plugin entry | iOS sign in cannot complete, because nothing registered the URL scheme it returns through |
| Plugin entry added with no iOS client id to put in it | `eas build` fails at prebuild. Do not add the entry until the client exists |

---

## The free tier

Expo's free plan includes a limited number of low-priority builds per month, reset monthly — enough for a pilot. Builds queue behind paying customers, so expect to wait. Starter is $19/month for build credit if the wait becomes tedious.

## CI

`.github/workflows/ci.yml` runs `npx tsc --noEmit` on `mobile/`. That will now type-check against React 19 and Navigation 7, so **the mobile CI job is the first real signal on this upgrade** — if it goes red, the fixes belong in this PR before merge.
