/* What a social account's chip may claim, and what may be said under its
   follower number.

   WHY THIS FILE EXISTS. Both halves fail silently and both fail toward the
   same kind of harm: a brand believing a number. Collapse connected into
   pending and the creator who actually authorised Facebook is shown the badge
   of somebody who typed a name into a box. Widen verified to cover a social
   login and a brand is told an identity document was checked when none was.
   Leave a self-reported count unmarked and it renders exactly like one read
   back through the creator's own OAuth token, which is the state this whole
   change exists to end. None of the four throws, none logs, and every one of
   them reads on screen as a perfectly ordinary profile.

   IT HAS TO LIVE UNDER mobile/tests/. The include glob in vitest.config.ts
   collects test files under tests/ and nowhere else, so the same file under
   mobile/src/ would be collected by nothing and would pass by never running,
   which is the note punctuation.test.ts, socialConnect.test.ts and
   socialPages.test.ts all carry for the same reason. */
import { describe, expect, it } from "vitest";

import { formatDate } from "../src/lib/dates";
import { followerNote, socialStatusChip } from "../src/lib/socialStatus";

describe("the chip on a social account", () => {
  it("gives a connected account a chip of its own, not the pending one", () => {
    /* The live defect: a creator who signed in, granted the permissions and
       chose their Page was shown "En attente". */
    const chip = socialStatusChip("connected");
    expect(chip.key).toBe("profile.socialStatusConnected");
    expect(chip.key).not.toBe(socialStatusChip("pending").key);
  });

  it("never lets a connected account borrow the verified label", () => {
    /* A social login proves control of a handle. It says nothing at all
       about who is holding it, which is what verified promises. */
    expect(socialStatusChip("connected").key).not.toBe("profile.verified");
    expect(socialStatusChip("connected").tone).not.toBe("strong");
  });

  it("keeps verified stronger than connected, because it is a bigger claim", () => {
    expect(socialStatusChip("verified")).toEqual({ key: "profile.verified", tone: "strong" });
    expect(socialStatusChip("connected").tone).toBe("quiet");
  });

  it("says an admin refused an account instead of calling it pending", () => {
    expect(socialStatusChip("rejected")).toEqual({
      key: "profile.socialStatusRejected",
      tone: "bad",
    });
  });

  it("still calls a typed handle pending", () => {
    expect(socialStatusChip("pending")).toEqual({ key: "profile.pending", tone: "neutral" });
  });

  it("understates a status it has never heard of rather than overstating it", () => {
    /* A value this build does not know can only come from a backend newer
       than the app. Shown as waiting it disappoints; shown as checked it
       would be a lie somebody spends money on. */
    for (const status of ["", "some_future_state", null, undefined]) {
      const chip = socialStatusChip(status);
      expect(chip.key).toBe("profile.pending");
      expect(chip.tone).toBe("neutral");
    }
  });
});

describe("the line under a follower number", () => {
  const CHECKED = {
    follower_count: 1688,
    follower_source: "platform_api",
    follower_verified_at: "2026-09-19T08:12:00",
  };
  const TYPED = {
    follower_count: 1688,
    follower_source: "self_reported",
    follower_verified_at: null,
  };

  it("marks a platform read number as checked and dates it", () => {
    const note = followerNote(CHECKED, "en");
    expect(note).not.toBeNull();
    expect(note?.key).toBe("profile.socialFollowersChecked");
    expect(note?.checked).toBe(true);
    expect(note?.date).not.toBe("");
  });

  it("writes that date through formatDate in the reader's language", () => {
    /* Not an assertion on the spelling of a day: the point is that the raw
       naive-UTC string never reaches a screen, and that the language given
       to the helper is the one the date is written in. */
    for (const language of ["fr", "en"]) {
      const note = followerNote(CHECKED, language);
      expect(note?.date).toBe(formatDate(CHECKED.follower_verified_at, language));
      expect(note?.date).not.toContain("T");
      expect(note?.date).toMatch(/^\d{2}\/\d{2}\/\d{4}$/);
    }
  });

  it("says a typed number is the creator's own, and never says verified", () => {
    const note = followerNote(TYPED, "fr");
    expect(note?.key).toBe("profile.socialFollowersSelf");
    expect(note?.checked).toBe(false);
    expect(note?.date).toBe("");
  });

  it("marks both sides, so neither is left to be inferred", () => {
    /* The defect being fixed was not a missing badge on one side. It was
       that a checked figure and a claimed one were the same pixels. */
    const checked = followerNote(CHECKED, "en");
    const typed = followerNote(TYPED, "en");
    expect(checked).not.toBeNull();
    expect(typed).not.toBeNull();
    expect(checked?.key).not.toBe(typed?.key);
    expect(checked?.checked).not.toBe(typed?.checked);
  });

  it("says nothing at all about a row written before the column existed", () => {
    /* A null source is not "self reported". It is "we do not know", because
       backend #161 added the column after those rows were stored. Captioning
       them either way would invent a fact, so they carry no marker and the
       set shrinks as accounts are edited or reconnected. */
    expect(followerNote({ follower_count: 1688, follower_source: null }, "en")).toBeNull();
    expect(followerNote({ follower_count: 1688 }, "en")).toBeNull();
  });

  it("says nothing about a source value it does not recognise", () => {
    expect(followerNote({ follower_count: 1688, follower_source: "guessed" }, "en")).toBeNull();
  });

  it("says nothing when there is no number to caption", () => {
    /* A sentence about where a figure came from, under no figure, describes
       nothing. The backend writes a null source beside a null count for the
       same reason. */
    expect(followerNote({ follower_count: null, follower_source: "self_reported" }, "en")).toBeNull();
    expect(followerNote({ follower_source: "platform_api", follower_verified_at: "2026-09-19T08:12:00" }, "en")).toBeNull();
  });

  it("captions a count of zero, which is a figure a platform really reports", () => {
    const note = followerNote({ ...CHECKED, follower_count: 0 }, "en");
    expect(note?.checked).toBe(true);
  });

  it("keeps the claim but drops the date when a checked number carries none", () => {
    /* Should not happen: the backend writes source and timestamp together.
       If it ever does, the claim is still true and only the date is gone. */
    const note = followerNote({ ...CHECKED, follower_verified_at: null }, "en");
    expect(note?.key).toBe("profile.socialFollowersCheckedUndated");
    expect(note?.checked).toBe(true);
    expect(note?.date).toBe("");
  });

  it("refuses a count that is not a usable number instead of captioning NaN", () => {
    /* The value comes off a JSON body, so the type is a claim rather than a
       guarantee. */
    expect(followerNote({ ...CHECKED, follower_count: Number.NaN }, "en")).toBeNull();
    expect(followerNote({ ...CHECKED, follower_count: "1688" as unknown as number }, "en")).toBeNull();
  });
});
