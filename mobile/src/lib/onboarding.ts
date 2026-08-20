/* Has this handset already been through the pre-auth intro?

   STORED WHERE THE TOKEN IS STORED. The app has exactly one persistence
   mechanism — expo-secure-store, the device keystore — and lib/auth.tsx keeps
   the JWT there while lib/language.ts keeps the language override there. A
   boolean is not a reason to introduce a second one: AsyncStorage would be a
   new dependency, a second thing to clear on logout-and-reinstall questions,
   and a second answer to "where does this app keep its state".

   The keystore is asynchronous, so the value is also held in a module-level
   cache. RootNavigator reads that cache DURING RENDER to choose the signed-out
   stack's initial route, and it has to be able to: a logout later in the same
   session must land on Login, and it would not if the decision were waiting on
   a fresh keystore round trip while the navigator was already mounting. */
import * as SecureStore from "expo-secure-store";

const KEY = "kolabo.landingSeen";

/* null = not read yet. The navigator gates its first render on this being
   settled, which is why the tri-state is worth having over a plain false. */
let cached: boolean | null = null;

export function landingSeenCached(): boolean | null {
  return cached;
}

export async function loadLandingSeen(): Promise<boolean> {
  if (cached !== null) return cached;
  let seen = false;
  try {
    seen = (await SecureStore.getItemAsync(KEY)) === "1";
  } catch {
    /* A keystore that will not answer is read as "never seen". Showing the
       intro one time too many costs a swipe; suppressing it would hide the
       only signposted route to registration behind a failed read. */
    seen = false;
  }
  cached = seen;
  return seen;
}

/* Called when the reader leaves the intro through one of its two doors, NOT
   when the screen mounts. The flag records "this person has been through the
   intro and chosen", so an app killed halfway through the carousel still
   shows it next launch — and anyone who has ever reached Login or Register
   from it never sees it again, which is the behaviour the returning
   signed-out user needs. */
export async function markLandingSeen(): Promise<void> {
  // In memory first and synchronously: see the note about render-time reads.
  cached = true;
  try {
    await SecureStore.setItemAsync(KEY, "1");
  } catch {
    // Persistence is a nicety; this session has already moved on.
  }
}
