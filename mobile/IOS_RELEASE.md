# Kolabo on iOS — what it takes to get a build onto an iPhone

Android is done: `eas build -p android --profile preview` produces an APK anyone can sideload,
no account, no review, no gatekeeper. **iOS has no equivalent.** Every route to a physical
iPhone — TestFlight, ad-hoc, App Store — runs through a paid Apple Developer Program account.
The only free option is a simulator build, and a simulator only exists on a Mac.

So the work splits into two tracks that run in parallel:

- **Track A — the account.** Only you can do this, it costs money, and it has a queue.
- **Track B — the app.** Config and store-readiness work that can be done before the account exists.

Track A is the long pole. Start it first even though nothing depends on it yet.

---

## Track A — Apple Developer Program

**Cost: US $99/year**, renewed annually. There is no free tier and no one-off purchase.

### Individual or organisation — decide before you start

| | Individual | Organisation |
|---|---|---|
| Seller name on the App Store | Your legal name | The company name |
| What Apple needs | Government ID | **D-U-N-S number** + proof the entity is a legal business + proof you can bind it |
| Typical time to approve | Hours to a couple of days | **Commonly 1–3 weeks**, mostly waiting on D-U-N-S |
| Team members | Just you | Multiple, with roles |
| Switching later | — | Migrating individual → organisation is possible but is a support ticket, not a button |

For a marketplace that takes other people's money, **"Kolabo" as the seller name reads very
differently from "Tairou Mocktar" as the seller name**. That argues for organisation enrolment.
It also argues for starting now, because the D-U-N-S lookup is the slow part and it is free.

Getting a D-U-N-S number for a Benin-registered entity is not always instant — Dun & Bradstreet
coverage varies by country. Apple has a D-U-N-S lookup tool in the enrolment flow that will tell
you whether one already exists for the company. If none exists, you request one; that request is
where the 1–3 weeks goes.

**Practical order:**

1. Look up whether the company already has a D-U-N-S number (Apple's enrolment flow does this).
2. If not, request one. Free.
3. Enrol as an organisation once it comes back.
4. If the entity is not registered yet and you need to test on iOS *now*, enrol as an individual
   to unblock TestFlight, and plan the migration later. This is a real trade-off, not a free move.

### While you wait

Nothing in Track B is blocked by this. Do it in the meantime.

---

## Track B — what the app needs before Apple sees it

### 1. The bundle identifier is permanent — decide it first

`app.json` currently says `com.kolabo.app` for both platforms. **This is a placeholder.**

Once an app is published under a bundle ID, that ID cannot be changed. Changing it means
publishing a *different* app and losing every install, rating and review on both stores.
Changing it today costs nothing.

Convention is reverse-DNS of a domain you actually control:

- `com.mocktar.kolabo` — works today, but bakes a personal domain into the company's app forever.
- `com.kolaboafrica.app` — the natural choice once `kolaboafrica.com` is registered (KOL-40,
  verified available at the time of that check; re-check before relying on it).

**This is a founder decision and it is now on the critical path.** It has to be settled before the
first TestFlight upload, not after.

### 2. App icon — required for the App Store, currently absent

`app.json` has no `icon` key, so `expo prebuild` emits `» ios: icon: No icon is defined in the
Expo config` and falls back to Expo's blank default. Verified: the generated Xcode project does
contain `App-Icon-1024x1024@1x.png`, so **a build will not fail** — it will just carry a
placeholder icon.

That is survivable for internal TestFlight. It is not survivable for a public listing.
Needed: a single **1024×1024 PNG, no alpha channel, no rounded corners** (Apple applies the mask),
referenced as `"icon": "./assets/icon.png"`. Expo generates every other size from it.

### 3. Permissions — fixed, and it also fixed an Android problem

Before this change, `expo prebuild` was generating three iOS permission prompts:

```
NSCameraUsageDescription      "Allow Kolabo to access your camera"
NSMicrophoneUsageDescription  "Allow Kolabo to access your microphone"
NSPhotoLibraryUsageDescription "Allow Kolabo to access your photos"
```

Two problems with that. First, the app never uses the camera or the microphone —
`src/lib/imagePicker.ts` calls only `launchImageLibraryAsync`. Declaring permissions you do not
use is a documented App Review rejection reason and it makes the App Privacy questionnaire harder
to answer honestly. Second, the strings are `expo-image-picker`'s generic defaults; Apple's
guideline 5.1.1 asks the purpose string to say *why*, and boilerplate strings get flagged.

`app.json` now configures the plugin explicitly:

```json
["expo-image-picker", {
  "photosPermission": "Kolabo needs access to your photos so you can add a profile picture and upload the content you deliver for a campaign.",
  "cameraPermission": false,
  "microphonePermission": false
}]
```

Verified by running `expo prebuild` against both platforms:

- iOS `Info.plist` now contains **exactly one** usage description, the photo one, with the real
  purpose string.
- Android's merged manifest now marks `android.permission.CAMERA` and
  `android.permission.RECORD_AUDIO` as `tools:node="remove"`. **The APK you have been installing
  was requesting microphone access.** That would have been a question mark on the Play Store data
  safety form too.

### 4. Bilingual permission prompts

The app is EN/FR, so the permission prompt should be too. `app.json` now has:

```json
"locales": { "en": "./locales/en.json", "fr": "./locales/fr.json" }
```

Verified: prebuild generates `ios/Kolabo/Supporting/en.lproj/InfoPlist.strings` and
`fr.lproj/InfoPlist.strings`, and the Xcode project references them. A francophone user in
Cotonou now gets the French prompt.

This mechanism is **iOS-only** and covers `Info.plist` strings and the display name — it is not a
replacement for the in-app i18n, which already works.

### 5. Payments — expect App Review to ask

Apple's In-App Purchase rule (guideline 3.1.1) applies to digital content consumed inside the app.
Kolabo sells **a real-world service between two people** — a creator producing and posting content
for a business. That is the same category as Fiverr, Upwork, Airbnb and Uber, which all take
payment outside IAP under guideline 3.1.3(e) / 3.1.5. FedaPay hosted checkout is therefore the
correct mechanism, not a violation.

That said, a reviewer seeing a payment sheet in a marketplace app will look at it. Put a plain
explanation in the **App Review Notes** field: what is being bought, that the deliverable is
content published on the creator's own social channels off-platform, and that funds are held in
escrow and released to the creator. Saying it up front is much cheaper than a rejection round-trip.

Note also that platform **subscriptions** (premium creator / premium business plans, per the
product spec) are a different question — a subscription unlocking in-app features is much closer
to IAP territory. That decision does not need to be made for the pilot, but do not assume the
FedaPay answer carries over to it.

### 6. Things App Review will reject on that are already handled

Checked, present, no action needed:

- **In-app account deletion** (guideline 5.1.1(v)) — `AccountScreen.tsx` has a password-confirmed
  delete flow with an explicit warning. Apps that let you create an account and not delete one get
  rejected.
- **Sign in with Apple** (guideline 4.8) — only triggered if the app offers third-party social
  login. Mobile login is email + password only, so this does not apply. **It will apply the day
  Google or Facebook login is added to the app**, and it is not a small feature.
- **Privacy manifest** — Expo SDK 54 generates `PrivacyInfo.xcprivacy` for its own modules; the app
  uses no third-party SDKs outside the Expo ecosystem.

Still to do, and only you can do it:

- **A working demo account** in App Review Notes — email, password, and enough seeded data that a
  reviewer can see a campaign and a contract. Reviewers reject apps they cannot get into. Given
  Kolabo has two distinct roles, supply **both** a creator and a business login.
- **Privacy policy URL** — mandatory field in App Store Connect, must be live before submission.
- **The App Privacy questionnaire** — must match what the app actually collects (email, phone,
  photos, payment identifiers, messages).

---

## The build commands, once the account exists

No Mac required — EAS builds on macOS in the cloud and handles certificates and provisioning
profiles for you.

```bash
cd mobile

# First iOS build: EAS will prompt for Apple credentials and generate
# the distribution certificate and provisioning profile.
eas build -p ios --profile production

# Upload to TestFlight
eas submit -p ios --latest
```

**Use `production`, not `preview`, for TestFlight.** The `preview` profile is
`distribution: internal`, which on iOS means an ad-hoc build — that requires every tester's device
UDID registered in advance and is genuinely painful. TestFlight avoids all of it.

`eas.json` already sets `appVersionSource: "remote"`, so EAS increments the iOS build number
automatically. Apple rejects re-uploads of a build number it has already seen, and this is the
usual cause.

### TestFlight, briefly

- **Internal testers** — up to 100 people, and they must be users on your App Store Connect team.
  **No Beta App Review**, builds are available within minutes of processing. This is your loop.
- **External testers** — up to 10,000, via a public link or email invite. The **first** build a
  group tests goes through Beta App Review (lighter than full App Store review, but a queue).
  This is how you get testers in Cotonou, Lomé and Accra who are not on your team.

Builds expire after 90 days.

---

## Realistic sequence

| Order | Step | Blocked by | Who |
|---|---|---|---|
| 1 | Look up / request D-U-N-S number | — | Founder |
| 2 | Decide the bundle identifier | — | Founder |
| 3 | Produce the 1024×1024 app icon | Brand direction | Design |
| 4 | Enrol in Apple Developer Program | D-U-N-S (org route) | Founder |
| 5 | Write privacy policy, host it | — | Founder + legal review |
| 6 | Seed creator + business demo accounts on the dev API | — | Dev |
| 7 | Create the app record in App Store Connect | Steps 2 and 4 | Dev |
| 8 | `eas build -p ios --profile production` | Step 7 | Dev |
| 9 | `eas submit -p ios --latest` → internal TestFlight | Step 8 | Dev |
| 10 | External TestFlight group → Beta App Review | Steps 5, 6, 9 | Dev |

Steps 1–3, 5 and 6 are all doable today. Nothing after step 4 is.

---

## Unverified / needs confirmation

- Apple's $99 fee and the TestFlight tester limits above are Apple's published figures at the time
  of writing; confirm on developer.apple.com before budgeting.
- Whether a D-U-N-S number already exists for the Kolabo entity, and whether the entity is
  registered at all, is unknown here.
- `kolaboafrica.com` was verified available at the time of the KOL-40 check. Availability changes.
  Re-check before deciding the bundle ID on the strength of it.
- Nothing in this document has been through an actual App Review. The rejection reasons listed are
  the well-documented common ones, not a guarantee of approval.
