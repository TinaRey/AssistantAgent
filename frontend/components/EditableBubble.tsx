"use client";
import { useState } from "react";
import { useCopy } from "@/lib/useCopy";
import type { Message } from "@/lib/types";
import { Markdown } from "./Markdown";

/** Any assistant reply can be copied or rewritten by hand, even if it is plain chat text. */
export function EditableBubble({ message, onSave }: { message: Message; onSave: (content: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(message.content);
  const { copied, copy } = useCopy();

  if (editing) {
    return (
      <div className="bubble editing">
        <textarea
          rows={Math.min(18, Math.max(5, text.split("\n").length + 1))}
          value={text} onChange={(e) => setText(e.target.value)} aria-label="Modifier la réponse"
        />
        <div className="actions">
          <button className="primary" disabled={!text.trim()} onClick={() => { onSave(text.trim()); setEditing(false); }}>Enregistrer</button>
          <button onClick={() => { setText(message.content); setEditing(false); }}>Annuler</button>
        </div>
      </div>
    );
  }
  return (
    <div className="bubble">
      <Markdown>{message.content}</Markdown>
      <div className="bubble-actions">
        <button className="link" onClick={() => { setText(message.content); setEditing(true); }}>✎ Modifier</button>
        <button className="link" onClick={() => copy(message.content)}>{copied ? "Copié ✓" : "Copier"}</button>
        {message.edited && <span className="muted">modifié par vous</span>}
      </div>
    </div>
  );
}
