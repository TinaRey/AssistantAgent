"use client";
import { useState } from "react";
import { useCopy } from "@/lib/useCopy";
import type { Artifact } from "@/lib/types";
import type { DraftProps } from "./ArtifactView";
import { ReviseBox } from "./ReviseBox";

type Post = { text: string; hashtags: string[]; visual_suggestion?: string | null };
/** Post text followed by its hashtags, skipping any the text already contains (older cards had duplicates). */
function originalText(p: Post): string {
  const tags = p.hashtags
    .map((t) => (t.startsWith("#") ? t : `#${t.replace(/\s+/g, "")}`))
    .filter((t, i, all) => all.indexOf(t) === i && !p.text.toLowerCase().includes(t.toLowerCase()));
  return `${p.text}\n\n${tags.join(" ")}`.trim();
}

export function LinkedInPreview({
  artifact, busy, onEdit, onRevise, startIndex = 1,
}: { artifact: Artifact; startIndex?: number } & DraftProps) {
  const posts = artifact.data.posts as Post[];
  const originals = posts.map(originalText);
  const [texts, setTexts] = useState<string[]>(artifact.edits?.texts ?? originals);
  const [saved, setSaved] = useState(!!artifact.edits);

  const save = (next: string[]) => {
    const changed = next.some((t, i) => t !== originals[i]);
    onEdit(artifact.call_id, changed ? { texts: next } : undefined);
    setSaved(true);
  };

  return (
    <>
      {posts.map((post, i) => (
        <PostCard
          key={i} post={post} index={startIndex + i} text={texts[i]} original={originals[i]} saved={saved} busy={busy}
          onChange={(v) => { setTexts(texts.map((t, j) => (j === i ? v : t))); setSaved(false); }}
          onBlur={() => save(texts)}
          onReset={() => { const next = texts.map((t, j) => (j === i ? originals[i] : t)); setTexts(next); save(next); }}
          onRevise={(instruction) =>
            onRevise(`Modifie ce post LinkedIn : ${instruction}`, `Version actuelle du post (modifiée par l'utilisatrice, à utiliser comme base) :\n${texts[i]}`)
          }
        />
      ))}
    </>
  );
}

function PostCard({
  post, index, text, original, saved, busy, onChange, onBlur, onReset, onRevise,
}: {
  post: Post; index: number; text: string; original: string; saved: boolean; busy: boolean;
  onChange: (v: string) => void; onBlur: () => void; onReset: () => void; onRevise: (i: string) => void;
}) {
  const { copied, copy } = useCopy();
  const edited = text !== original;
  return (
    <section className="card">
      <h3>
        Post LinkedIn #{index}
        {edited && <span className="tag edited">modifié par vous</span>}
      </h3>
      <textarea rows={9} value={text} onChange={(e) => onChange(e.target.value)} onBlur={onBlur} aria-label={`Post ${index}`} />
      {post.visual_suggestion && <p className="muted">Visuel suggéré : {post.visual_suggestion}</p>}
      <div className="actions">
        <button onClick={() => copy(text)}>{copied ? "Copié ✓" : "Copier"}</button>
        {edited && <button className="link" onClick={onReset}>Rétablir la version d'origine</button>}
        <span className="muted">
          {edited ? (saved ? "Modifications enregistrées ✓" : "…") : "Modifiable · publication manuelle sur LinkedIn."}
        </span>
      </div>
      <ReviseBox busy={busy} placeholder="Ex. : plus court, ton plus direct, ajoute une question…" onSubmit={onRevise} />
    </section>
  );
}
