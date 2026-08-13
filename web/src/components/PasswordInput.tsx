import { useState, type InputHTMLAttributes } from "react";

/* A password field with its own eyes. The input is the ordinary .input in
   every way — same class, same props through — plus a show/hide toggle,
   because a password typed blind is how typos become lockouts, and every
   phone keyboard user especially deserves to be able to check what they
   wrote. Each field hides or shows independently: revealing one password
   never reveals another on the same screen.

   The button is type="button" so it can never submit the form it sits in,
   and aria-pressed + labels keep the toggle readable to a screen reader. */
export function PasswordInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const [shown, setShown] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <input
        {...props}
        className={props.className ?? "input"}
        type={shown ? "text" : "password"}
        style={{ paddingRight: 42, width: "100%", ...props.style }}
      />
      <button
        type="button"
        onClick={() => setShown((v) => !v)}
        aria-pressed={shown}
        aria-label={shown ? "Hide password" : "Show password"}
        title={shown ? "Hide password" : "Show password"}
        style={{
          position: "absolute",
          right: 6,
          top: 0,
          bottom: 0,
          margin: "auto 0",
          height: 30,
          width: 32,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "var(--muted)",
          fontSize: 16,
          lineHeight: 1,
        }}
      >
        {/* An inline glyph rather than an icon dependency: the web bundle has
            no icon set today, and one character is not a reason to add one. */}
        {shown ? "🙈" : "👁"}
      </button>
    </div>
  );
}
