"use client";
import { useEffect, useRef } from "react";
import type { Message } from "@/lib/types";
import { ArtifactView } from "./ArtifactView";
import { PendingActionCard } from "./PendingActionCard";

const SUGGESTIONS = [
  "Fais des recherches sur Urgo et identifie des pistes de collaboration.",
  "Rédige trois posts LinkedIn sur nos derniers produits.",
  "Prépare un email de présentation pour une entreprise.",
];

export function MessageList({
  messages, loading, onSuggest,
}: { messages: Message[]; loading: boolean; onSuggest: (t: string) => void }) {
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
          {m.content && <p className="bubble">{m.content}</p>}
          {m.artifacts?.map((a) => <ArtifactView key={a.call_id} artifact={a} />)}
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
