"use client";
import { useState } from "react";
import { useCopy } from "@/lib/useCopy";
import type { DraftProps } from "./ArtifactView";
import type { Artifact } from "@/lib/types";
import { ReviseBox } from "./ReviseBox";

export function EmailPreview({ artifact, busy, onEdit, onRevise }: { artifact: Artifact } & DraftProps) {
  const original = { to: artifact.data.to ?? "", subject: artifact.data.subject as string, body: artifact.data.body as string };
  const [draft, setDraft] = useState(artifact.edits ?? original);
  const [saved, setSaved] = useState(!!artifact.edits);
  const { copied, copy } = useCopy();
  const edited = draft.to !== original.to || draft.subject !== original.subject || draft.body !== original.body;

  const change = (k: "to" | "subject" | "body", v: string) => { setDraft({ ...draft, [k]: v }); setSaved(false); };
  const save = () => {
    if (saved) return;
    onEdit(artifact.call_id, edited ? draft : undefined);
    setSaved(true);
  };
  const reset = () => { setDraft(original); onEdit(artifact.call_id, undefined); setSaved(false); };

  const mailto = `mailto:${encodeURIComponent(draft.to)}?subject=${encodeURIComponent(draft.subject)}&body=${encodeURIComponent(draft.body)}`;
  const current = `À : ${draft.to || "(non renseigné)"}\nObjet : ${draft.subject}\n\n${draft.body}`;

  return (
    <section className="card">
      <h3>
        Brouillon d'email <span className="tag">à relire avant envoi</span>
        {edited && <span className="tag edited">modifié par vous</span>}
      </h3>
      <label>À<input value={draft.to} onChange={(e) => change("to", e.target.value)} onBlur={save} placeholder="Destinataire (à renseigner)" /></label>
      <label>Objet<input value={draft.subject} onChange={(e) => change("subject", e.target.value)} onBlur={save} /></label>
      <label>Message<textarea rows={10} value={draft.body} onChange={(e) => change("body", e.target.value)} onBlur={save} /></label>
      {!draft.to && <p className="muted">Aucune adresse vérifiée : ajoutez-la vous-même.</p>}
      <div className="actions">
        <button onClick={() => copy(`Objet : ${draft.subject}\n\n${draft.body}`)}>{copied ? "Copié ✓" : "Copier"}</button>
        <a className="button" href={mailto} onClick={save}>Ouvrir dans ma messagerie</a>
        {edited && <button className="link" onClick={reset}>Rétablir la version d'origine</button>}
        <span className="muted">{saved && edited ? "Modifications enregistrées ✓" : edited ? "…" : "Vous pouvez modifier le texte ci-dessus."}</span>
      </div>
      <ReviseBox
        busy={busy} placeholder="Ex. : plus court, plus formel, mentionne notre collection…"
        onSubmit={(instruction) =>
          onRevise(`Modifie cet email : ${instruction}`, `Version actuelle de l'email (modifiée par l'utilisatrice, à utiliser comme base) :\n${current}`)
        }
      />
    </section>
  );
}
