"use client";
import { useCallback, useRef, useState } from "react";
import { ApiError, sendChat } from "@/lib/api";
import type { Message } from "@/lib/types";

type Update = (id: string, fn: (m: Message[]) => Message[]) => void;

export function useChat(conversationId: string | undefined, messages: Message[], update: Update) {
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!conversationId || !content || inFlight.current) return;
      inFlight.current = true;
      setLoading(true);
      const userMsg: Message = { id: crypto.randomUUID(), role: "user", content };
      update(conversationId, (m) => [...m, userMsg]);
      try {
        // Errors are UI-only: they are not replayed to the model.
        const history = [...messages.filter((m) => !m.error), userMsg];
        const res = await sendChat(history);
        update(conversationId, (m) => [
          ...m,
          {
            id: crypto.randomUUID(), role: "assistant", content: res.reply,
            traces: res.tool_calls, artifacts: res.artifacts, pending: res.pending_actions,
          },
        ]);
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "Impossible de joindre le serveur.";
        update(conversationId, (m) => [
          ...m,
          { id: crypto.randomUUID(), role: "assistant", content: msg, error: true },
        ]);
      } finally {
        inFlight.current = false;
        setLoading(false);
      }
    },
    [conversationId, messages, update],
  );

  return { send, loading };
}
