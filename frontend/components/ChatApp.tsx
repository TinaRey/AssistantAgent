"use client";
import { useConversations } from "@/hooks/useConversations";
import { useChat } from "@/hooks/useChat";
import { logout } from "@/lib/api";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";
import { Sidebar } from "./Sidebar";

export function ChatApp() {
  const { conversations, active, ready, setActiveId, create, remove, update } = useConversations();
  const { send, loading } = useChat(active?.id, active?.messages ?? [], update);

  async function signOut() {
    await logout().catch(() => undefined);
    window.location.href = "/login";
  }

  if (!ready || !active) return <p className="muted center">Chargement…</p>;

  return (
    <div className="app">
      <Sidebar
        conversations={conversations} activeId={active.id}
        onSelect={setActiveId} onNew={create} onDelete={remove} onSignOut={signOut}
      />
      <section className="chat">
        <MessageList messages={active.messages} loading={loading} onSuggest={send} />
        <Composer onSend={send} disabled={loading} />
      </section>
    </div>
  );
}
