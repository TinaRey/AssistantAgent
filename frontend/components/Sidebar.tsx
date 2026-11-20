import { conversationTitle, type Conversation } from "@/lib/types";
import Link from "next/link";
import { SidebarResizer } from "./SidebarResizer";

type Props = {
  conversations: Conversation[]; activeId: string;
  onSelect: (id: string) => void; onNew: () => void;
  onDelete: (id: string) => void; onSignOut: () => void;
  width: number; onResize: (w: number) => void; onResetWidth: () => void;
};

export function Sidebar({
  conversations, activeId, onSelect, onNew, onDelete, onSignOut, width, onResize, onResetWidth,
}: Props) {
  const emptyCount = conversations.filter((c) => c.messages.length === 0).length;
  return (
    <aside className="sidebar">
      <h1>Pantalelle</h1>
      <button className="primary" onClick={onNew}>+ Nouvelle conversation</button>
      <Link className="navlink" href="/documents">📄 Documents Pantalelle</Link>
      <nav aria-label="Conversations">
        {conversations.map((c) => {
          const title = conversationTitle(c);
          // An empty chat is deletable only when there are several empty ones.
          const canDelete = c.messages.length > 0 || emptyCount > 1;
          return (
          <div key={c.id} className={`conv ${c.id === activeId ? "active" : ""}`}>
            <button className="conv-title" title={title} onClick={() => onSelect(c.id)}>{title}</button>
            {canDelete && (
              <button
                className="icon" title="Supprimer" aria-label={`Supprimer ${title}`}
                onClick={() => confirm("Supprimer cette conversation ?") && onDelete(c.id)}
              >×</button>
            )}
          </div>
          );
        })}
      </nav>
      <button className="link" onClick={onSignOut}>Se déconnecter</button>
      <SidebarResizer width={width} onResize={onResize} onReset={onResetWidth} />
    </aside>
  );
}
