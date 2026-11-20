import type { Conversation } from "@/lib/types";

type Props = {
  conversations: Conversation[]; activeId: string;
  onSelect: (id: string) => void; onNew: () => void;
  onDelete: (id: string) => void; onSignOut: () => void;
};

export function Sidebar({ conversations, activeId, onSelect, onNew, onDelete, onSignOut }: Props) {
  return (
    <aside className="sidebar">
      <h1>Pantalelle</h1>
      <button className="primary" onClick={onNew}>+ Nouvelle conversation</button>
      <nav aria-label="Conversations">
        {conversations.map((c) => (
          <div key={c.id} className={`conv ${c.id === activeId ? "active" : ""}`}>
            <button className="conv-title" onClick={() => onSelect(c.id)}>{c.title}</button>
            <button
              className="icon" aria-label={`Supprimer ${c.title}`}
              onClick={() => confirm("Supprimer cette conversation ?") && onDelete(c.id)}
            >×</button>
          </div>
        ))}
      </nav>
      <button className="link" onClick={onSignOut}>Se déconnecter</button>
    </aside>
  );
}
