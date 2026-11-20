import { conversationTitle, type Conversation } from "@/lib/types";
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
  return (
    <aside className="sidebar">
      <h1>Pantalelle</h1>
      <button className="primary" onClick={onNew}>+ Nouvelle conversation</button>
      <nav aria-label="Conversations">
        {conversations.map((c) => {
          const title = conversationTitle(c);
          return (
          <div key={c.id} className={`conv ${c.id === activeId ? "active" : ""}`}>
            <button className="conv-title" title={title} onClick={() => onSelect(c.id)}>{title}</button>
            <button
              className="icon" title="Supprimer" aria-label={`Supprimer ${title}`}
              onClick={() => confirm("Supprimer cette conversation ?") && onDelete(c.id)}
            >×</button>
          </div>
          );
        })}
      </nav>
      <button className="link" onClick={onSignOut}>Se déconnecter</button>
      <SidebarResizer width={width} onResize={onResize} onReset={onResetWidth} />
    </aside>
  );
}
