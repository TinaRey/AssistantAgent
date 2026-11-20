"use client";
import { useState } from "react";
import { useCopy } from "@/lib/useCopy";

export function EmailPreview({ data }: { data: Record<string, any> }) {
  const [to, setTo] = useState<string>(data.to ?? "");
  const [subject, setSubject] = useState<string>(data.subject);
  const [body, setBody] = useState<string>(data.body);
  const { copied, copy } = useCopy();
  const mailto = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  return (
    <section className="card">
      <h3>Brouillon d'email <span className="tag">à relire avant envoi</span></h3>
      <label>À<input value={to} onChange={(e) => setTo(e.target.value)} placeholder="Destinataire (à renseigner)" /></label>
      <label>Objet<input value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
      <label>Message<textarea rows={10} value={body} onChange={(e) => setBody(e.target.value)} /></label>
      {!to && <p className="muted">Aucune adresse vérifiée : ajoutez-la vous-même.</p>}
      <div className="actions">
        <button onClick={() => copy(`Objet : ${subject}\n\n${body}`)}>{copied ? "Copié ✓" : "Copier"}</button>
        <a className="button" href={mailto}>Ouvrir dans ma messagerie</a>
      </div>
    </section>
  );
}
