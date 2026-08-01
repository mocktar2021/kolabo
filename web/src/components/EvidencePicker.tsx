/* Attaching images to a dispute — the opening statement's, or a message's.

   It reuses the profile media upload rather than owning one. Creators and
   brands already have a working image endpoint with an owner column, a size
   limit and a serving route; a dispute-only uploader would be a second of
   each, to hold exactly the same JPEGs. The server also checks ownership on
   the ids it is handed — attaching an image you did not upload would leak it
   to the other party and to every admin who reads the case — and uploading
   through the caller's own /profiles/{userId}/media is what makes that check
   pass by construction.

   Files are uploaded one at a time and on selection, not on submit. The ids
   are what the dispute endpoint wants, so they have to exist before the form
   is sent; doing it here also means a failed upload costs the person their
   photo and not their statement. */
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { mediaSrc, uploadFile } from "../lib/api";
import { useAuth } from "../lib/auth";
import { MAX_EVIDENCE_IMAGES } from "../lib/disputes";
import type { UploadedMedia } from "../lib/types";

export function EvidencePicker({
  items,
  onChange,
  disabled
}: {
  items: UploadedMedia[];
  onChange: (items: UploadedMedia[]) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const { token, userId } = useAuth();
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const room = MAX_EVIDENCE_IMAGES - items.length;

  async function pick(files: FileList | null) {
    if (!files || files.length === 0 || !userId) return;
    setError(null);
    if (room <= 0) {
      setError(t("dispute.evidenceMax", { n: MAX_EVIDENCE_IMAGES }));
      return;
    }
    // Silently truncated rather than refused: the person picked too many, and
    // dropping the tail is closer to what they meant than dropping the lot.
    const chosen = Array.from(files).slice(0, room);
    const added: UploadedMedia[] = [];
    try {
      for (let i = 0; i < chosen.length; i++) {
        setProgress({ done: i, total: chosen.length });
        added.push(
          await uploadFile<UploadedMedia>(`/profiles/${userId}/media`, chosen[i], token)
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("dispute.evidenceFailed"));
    } finally {
      setProgress(null);
      // Whatever did land is kept. A batch that failed on the fourth image
      // should not throw away the three that worked.
      if (added.length > 0) onChange([...items, ...added]);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div>
      <label className="label">{t("dispute.evidence")}</label>
      {items.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
          {items.map((item) => (
            <div key={item.id} style={{ position: "relative" }}>
              <img
                src={mediaSrc(item.url)}
                alt=""
                style={{ width: 72, height: 72, objectFit: "cover", borderRadius: 8, display: "block" }}
              />
              <button
                type="button"
                className="btn btn-ghost"
                disabled={disabled}
                aria-label={t("dispute.evidenceRemove")}
                onClick={() => onChange(items.filter((i) => i.id !== item.id))}
                style={{ position: "absolute", top: -6, right: -6, padding: "0 6px", fontSize: 12, background: "var(--surface)", borderRadius: 999 }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      <input
        ref={input}
        type="file"
        accept="image/*"
        multiple
        disabled={disabled || progress !== null || room <= 0}
        onChange={(e) => pick(e.target.files)}
        aria-label={t("dispute.evidenceAdd")}
      />
      {progress && (
        <p className="muted" style={{ fontSize: 13, margin: "6px 0 0" }}>
          {t("dispute.evidenceUploading", { done: progress.done + 1, total: progress.total })}
        </p>
      )}
      {room <= 0 && (
        <p className="muted" style={{ fontSize: 13, margin: "6px 0 0" }}>
          {t("dispute.evidenceMax", { n: MAX_EVIDENCE_IMAGES })}
        </p>
      )}
      {error && <p style={{ fontSize: 13, color: "var(--danger, #b00)", margin: "6px 0 0" }}>{error}</p>}
    </div>
  );
}
