import { useState } from "react";
import { useTranslation } from "react-i18next";

/* Overlay modal for sharing a creator page. Mirrors the HandleModal overlay
   pattern from Onboarding: click outside closes, clicks inside stay. */
export function ShareModal({ name, url, onClose }: { name: string; url: string; onClose: () => void }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can be unavailable (insecure context); the input stays
      // selectable as the fallback.
    }
  }

  const encoded = encodeURIComponent(url);
  /* WhatsApp first: it is the dominant sharing channel in the pilot markets
     (Benin and Togo), so it gets the top spot. */
  const targets = [
    { label: "WhatsApp", href: `https://wa.me/?text=${encoded}` },
    { label: "X", href: `https://twitter.com/intent/tweet?url=${encoded}` },
    { label: t("public.shareEmail"), href: `mailto:?subject=${encodeURIComponent(t("public.shareEmailSubject", { name }))}&body=${encoded}` }
  ];

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(21,24,36,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 20 }}
      onClick={onClose}>
      <div className="card" style={{ maxWidth: 460, width: "100%" }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>{t("public.shareTitle", { name })}</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="input" readOnly value={url} onFocus={(e) => e.currentTarget.select()} />
          <button className="btn btn-ghost" onClick={copy}>{copied ? t("public.copied") : t("public.copy")}</button>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
          {targets.map((s) => (
            <a key={s.label} className="btn btn-ghost" href={s.href} target="_blank" rel="noreferrer">{s.label}</a>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 18 }}>
          <button className="btn btn-primary" onClick={onClose}>{t("public.close")}</button>
        </div>
      </div>
    </div>
  );
}
