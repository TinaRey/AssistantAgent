"use client";
import { useState } from "react";

/** Asks the assistant to rewrite a draft; the user's current (edited) text is sent along. */
export function ReviseBox({
  busy, onSubmit, placeholder,
}: { busy: boolean; onSubmit: (instruction: string) => void; placeholder: string }) {
  const [text, setText] = useState("");
  function submit() {
    if (!text.trim() || busy) return;
    onSubmit(text.trim());
    setText("");
  }
  return (
    <form className="revise" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <input
        value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder}
        aria-label="Demander une modification à l'assistant"
      />
      <button type="submit" disabled={busy || !text.trim()}>Demander à l'assistant</button>
    </form>
  );
}
