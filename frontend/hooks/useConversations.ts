"use client";
import { useCallback, useEffect, useState } from "react";
import type { Conversation, Message } from "@/lib/types";

const KEY = "pantalelle.conversations.v1";
const newConversation = (): Conversation => ({
  id: crypto.randomUUID(), title: "Nouvelle conversation", messages: [], updatedAt: Date.now(),
});

/** Conversations live in this browser only (localStorage). */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let list: Conversation[] = [];
    try { list = JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { list = []; }
    if (list.length === 0) list = [newConversation()];
    setConversations(list);
    setActiveId(list[0].id);
    setReady(true);
  }, []);

  useEffect(() => {
    if (ready) localStorage.setItem(KEY, JSON.stringify(conversations));
  }, [conversations, ready]);

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0];

  const create = useCallback(() => {
    const c = newConversation();
    setConversations((prev) => [c, ...prev]);
    setActiveId(c.id);
  }, []);

  const remove = useCallback((id: string) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      return next.length ? next : [newConversation()];
    });
    setActiveId((cur) => (cur === id ? "" : cur));
  }, []);

  useEffect(() => {
    if (ready && !conversations.some((c) => c.id === activeId) && conversations.length) {
      setActiveId(conversations[0].id);
    }
  }, [ready, conversations, activeId]);

  const update = useCallback((id: string, fn: (messages: Message[]) => Message[]) => {
    setConversations((prev) =>
      prev
        .map((c) => {
          if (c.id !== id) return c;
          const messages = fn(c.messages);
          const firstUser = messages.find((m) => m.role === "user");
          const title = firstUser ? firstUser.content.slice(0, 40) : c.title;
          return { ...c, messages, title, updatedAt: Date.now() };
        })
        .sort((a, b) => b.updatedAt - a.updatedAt),
    );
  }, []);

  return { conversations, active, ready, setActiveId, create, remove, update };
}
