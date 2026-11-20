"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  addNote, ApiError, deleteDocument, listDocuments, uploadDocument, type KnowledgeDocument,
} from "@/lib/api";

const KIND: Record<string, string> = { pdf: "PDF", docx: "Word", txt: "Texte", md: "Texte", note: "Note" };
const fmtSize = (n: number) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} Ko` : `${(n / 1048576).toFixed(1)} Mo`);
const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "Impossible de joindre le serveur.");

export function DocumentsPanel() {
  const [docs, setDocs] = useState<KnowledgeDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const input = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try { setDocs(await listDocuments()); } catch (e) { setError(errMsg(e)); setDocs([]); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function upload(files: FileList | File[]) {
    setError(null);
    for (const file of Array.from(files)) {
      setBusy(`Analyse de « ${file.name} »…`);
      try { await uploadDocument(file); } catch (e) { setError(`${file.name} : ${errMsg(e)}`); }
    }
    setBusy(null);
    if (input.current) input.current.value = "";
    refresh();
  }

  async function saveNote(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy("Enregistrement de la note…");
    try { await addNote(title, text); setTitle(""); setText(""); } catch (err) { setError(errMsg(err)); }
    setBusy(null);
    refresh();
  }

  async function remove(d: KnowledgeDocument) {
    if (!confirm(`Supprimer « ${d.filename} » de la base de connaissances ?`)) return;
    try { await deleteDocument(d.id); refresh(); } catch (e) { setError(errMsg(e)); }
  }

  return (
    <main className="docs">
      <Link href="/" className="muted">← Retour au chat</Link>
      <h1>Documents Pantalelle</h1>
      <p className="muted">
        L'assistant s'appuie sur ces documents pour parler de Pantalelle (histoire, positionnement, ton, produits).
        Il ne s'appuiera sur rien d'autre.
      </p>

      {error && <p role="alert" className="error">{error}</p>}
      {busy && <p className="muted typing">{busy}</p>}

      <section
        className={`dropzone ${dragging ? "over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); upload(e.dataTransfer.files); }}
      >
        <p>Glissez vos fichiers ici (PDF, Word, TXT, MD · 10 Mo max)</p>
        <button disabled={!!busy} onClick={() => input.current?.click()}>Choisir des fichiers</button>
        <input
          ref={input} type="file" multiple hidden accept=".pdf,.docx,.txt,.md"
          onChange={(e) => e.target.files && upload(e.target.files)}
        />
      </section>

      <form className="card" onSubmit={saveNote}>
        <h3>Ajouter une note</h3>
        <p className="muted">Par exemple : le compte rendu de la réunion sur le positionnement ou l'histoire de la marque.</p>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Titre (ex. Réunion de présentation)" maxLength={120} />
        <textarea rows={7} value={text} onChange={(e) => setText(e.target.value)} placeholder="Collez ou écrivez le contenu ici…" />
        <div className="actions">
          <button className="primary" type="submit" disabled={!!busy || !title.trim() || !text.trim()}>Enregistrer la note</button>
        </div>
      </form>

      <section>
        <h2>Base de connaissances {docs && `(${docs.length})`}</h2>
        {docs === null && <p className="muted">Chargement…</p>}
        {docs?.length === 0 && <p className="muted">Aucun document pour l'instant.</p>}
        <ul className="doclist">
          {docs?.map((d) => (
            <li key={d.id}>
              <div>
                <strong>{d.filename}</strong>
                <span className="muted"> · {KIND[d.kind] ?? d.kind} · {fmtSize(d.size_bytes)} · {d.chunk_count} passage{d.chunk_count > 1 ? "s" : ""}</span>
              </div>
              <button className="icon" title="Supprimer" aria-label={`Supprimer ${d.filename}`} onClick={() => remove(d)}>×</button>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
