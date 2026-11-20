"use client";
import { useConversations } from "@/hooks/useConversations";
import { useChat } from "@/hooks/useChat";
import { useSidebarWidth } from "@/hooks/useSidebarWidth";
import { logout } from "@/lib/api";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";
import { Sidebar } from "./Sidebar";

export function ChatApp() {
  const { conversations, active, ready, setActiveId, create, remove, update } = useConversations();
  const sidebar = useSidebarWidth();
  const { send, loading } = useChat(active?.id, active?.messages ?? [], update);

  async function signOut() {
    await logout().catch(() => undefined);
    window.location.href = "/login";
  }

  if (!ready || !active) return <p className="muted center">Chargement…</p>;

  return (
    <div className="app" style={{ "--sidebar-w": `${sidebar.width}px` } as React.CSSProperties}>
      <Sidebar
        conversations={conversations} activeId={active.id}
        onSelect={setActiveId} onNew={create} onDelete={remove} onSignOut={signOut}
        width={sidebar.width} onResize={sidebar.setWidth} onResetWidth={sidebar.reset}
      />
      <section className="chat">
        <MessageList messages={active.messages} loading={loading} onSuggest={send} />
        <Composer onSend={send} disabled={loading} />
      </section>
    </div>
  );
}
