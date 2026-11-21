"use client";
import { useEffect, useRef } from "react";
import type { Message } from "@/lib/types";
import { Markdown } from "./Markdown";
import { EditableBubble } from "./EditableBubble";
import { ArtifactView } from "./ArtifactView";
import { PendingActionCard } from "./PendingActionCard";

const SUGGESTIONS = [
  "Fais des recherches sur Urgo et identifie des pistes de collaboration.",
  "Rédige trois posts LinkedIn sur nos derniers produits.",
  "Prépare un email de présentation pour une entreprise.",
];

export function MessageList({
  messages, loading, onSuggest, onEdit, onRevise, onEditMessage,
}: {
  messages: Message[]; loading: boolean; onSuggest: (t: string) => void;
  onEdit: (callId: string, edits: Record<string, any> | undefined) => void;
  onRevise: (instruction: string, context: string) => void;
  onEditMessage: (id: string, content: string) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  if (messages.length === 0) {
    return (
      <div className="messages empty">
        <h2>Comment puis-je vous aider ?</h2>
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => onSuggest(s)}>{s}</button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="messages" aria-live="polite">
      {messages.map((m) => (
        <article key={m.id} className={`msg ${m.role} ${m.error ? "failed" : ""}`}>
          {m.content && (
            m.role === "assistant" && !m.error
              ? <EditableBubble message={m} onSave={(c) => onEditMessage(m.id, c)} />
              : <div className="bubble">{m.content}</div>
          )}
          {m.artifacts?.map((a, i) => (
            <ArtifactView
              key={a.call_id} artifact={a} busy={loading} onEdit={onEdit} onRevise={onRevise}
              startIndex={postsBefore(m.artifacts!, i) + 1}
            />
          ))}
          {m.pending?.map((p) => <PendingActionCard key={p.id} action={p} />)}
          {m.traces && m.traces.length > 0 && <ToolActivity traces={m.traces} />}
        </article>
      ))}
      {loading && <p className="muted typing">L'assistant travaille… (une recherche peut prendre une minute)</p>}
      <div ref={end} />
    </div>
  );
}

const LABELS: Record<string, string> = {
  search_company: "Recherche entreprise", retrieve_knowledge: "Base de connaissances",
  generate_email: "Email", generate_presentation: "Présentation", generate_linkedin_post: "Post LinkedIn",
};

function ToolActivity({ traces }: { traces: Message["traces"] }) {
  return (
    <details className="activity">
      <summary>Outils utilisés ({traces!.length})</summary>
      <ul>
        {traces!.map((t) => (
          <li key={t.id}>
            {LABELS[t.tool] ?? t.tool} · {t.status === "ok" ? "réussi" : t.status === "timeout" ? "délai dépassé"
              : t.status === "pending_approval" ? "en attente de votre accord" : "échec"}
            {" "}({(t.duration_ms / 1000).toFixed(1)} s)
            {t.error && <span className="muted"> — {t.error}</span>}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Number of LinkedIn posts shown in earlier cards of the same message, so numbering never restarts at 1. */
function postsBefore(artifacts: NonNullable<Message["artifacts"]>, index: number): number {
  return artifacts
    .slice(0, index)
    .filter((a) => a.tool === "generate_linkedin_post")
    .reduce((n, a) => n + ((a.data.posts as unknown[])?.length ?? 0), 0);
}
