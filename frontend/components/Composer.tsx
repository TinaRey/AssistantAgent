"use client";
import { useState } from "react";

export function Composer({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
  const [text, setText] = useState("");

  function submit() {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText("");
  }

  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <textarea
        value={text} rows={2} placeholder="Écrivez votre demande…" aria-label="Votre message"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
        }}
      />
      <button type="submit" className="primary" disabled={disabled || !text.trim()}>Envoyer</button>
    </form>
  );
}
