import { useTranslation } from "react-i18next";
import { mediaSrc } from "../lib/api";
import { PLATFORM_LABELS } from "../lib/platforms";
import type { CreatorIdentity } from "../lib/types";
import { formatFollowers } from "./CreatorCard";

/* One creator, rendered the same way on every list a business reads.

   Identity is not a per-list decision. The backend stopped treating it as one
   (app/core/identity.py resolves the same four fields for favourites, campaign
   invitations and proposals), and this is the client half of that: one
   component, so a business comparing an invitation against a proposal is not
   quietly shown the same person two different ways — which is exactly what
   used to happen, with a raw user id on one list and a name on the other.

   Presentational on purpose: no fetching, no state, no link. The lists around
   it already know what a click on a row should do, and they do not agree.

   Every field is optional and each absence is answered separately, because a
   creator can be favourited or invited the day they sign up:
     - no photo falls back to the brand gradient, never a broken image;
     - no name falls back to "Créateur sans nom", because a missing display
       name is something the brand should notice rather than an id to decipher;
     - no audience renders nothing at all. An unknown audience is not a zero
       one, and printing "0" would put a number on a creator that nobody
       measured. */
export function CreatorChip({ creator }: { creator: CreatorIdentity }) {
  const { t } = useTranslation();
  const src = mediaSrc(creator.avatar_url);

  /* top_platform and top_follower_count are filled together server-side — the
     biggest single connected platform, never a sum across platforms, since
     the same person following on two networks would otherwise be counted
     twice. Both are tested anyway: a line reading "Instagram · -" would be
     worse than no line. formatFollowers is the app's existing compact format
     (12.3k, 1.2M), shared with the discovery cards so one creator does not
     read as two different sizes on two screens. */
  const audience =
    creator.top_follower_count !== null && creator.top_platform !== null
      ? `${PLATFORM_LABELS[creator.top_platform] ?? creator.top_platform} · ${formatFollowers(creator.top_follower_count)}`
      : null;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
      <span
        aria-hidden="true"
        style={{
          width: 32, height: 32, borderRadius: "50%", overflow: "hidden", flexShrink: 0,
          background: src ? "var(--surface-2)" : "var(--gradient-brand)", display: "inline-block"
        }}
      >
        {src && <img src={src} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />}
      </span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>{creator.display_name || t("campaign.unnamedCreator")}</div>
        {audience && <div className="muted" style={{ fontSize: 12.5 }}>{audience}</div>}
      </div>
    </div>
  );
}
