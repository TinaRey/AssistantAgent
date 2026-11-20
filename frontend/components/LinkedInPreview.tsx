"use client";
import { useState } from "react";
import { useCopy } from "@/lib/useCopy";

type Post = { text: string; hashtags: string[]; visual_suggestion?: string | null; tone?: string | null };

export function LinkedInPreview({ data }: { data: Record<string, any> }) {
  return (
    <>
      {(data.posts as Post[]).map((p, i) => <PostCard key={i} post={p} index={i + 1} />)}
    </>
  );
}

function PostCard({ post, index }: { post: Post; index: number }) {
  const [text, setText] = useState(`${post.text}\n\n${post.hashtags.join(" ")}`.trim());
  const { copied, copy } = useCopy();
  return (
    <section className="card">
      <h3>Post LinkedIn #{index} {post.tone && <span className="tag">{post.tone}</span>}</h3>
      <textarea rows={9} value={text} onChange={(e) => setText(e.target.value)} aria-label={`Post ${index}`} />
      {post.visual_suggestion && <p className="muted">Visuel suggéré : {post.visual_suggestion}</p>}
      <div className="actions">
        <button onClick={() => copy(text)}>{copied ? "Copié ✓" : "Copier"}</button>
        <span className="muted">Publication manuelle sur LinkedIn.</span>
      </div>
    </section>
  );
}
