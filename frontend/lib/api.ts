import type { ChatResponse, Message, PendingAction } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body instanceof FormData
      ? init?.headers
      : { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (res.status === 401 && path !== "/auth/login" && typeof window !== "undefined") {
    window.location.href = "/login";
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new ApiError(res.status, detail ?? friendlyStatus(res.status));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function friendlyStatus(status: number): string {
  if (status === 429) return "Trop de requêtes. Réessayez dans un instant.";
  if (status === 504) return "L'assistant a mis trop de temps à répondre.";
  if (status >= 500) return "Le service est momentanément indisponible.";
  return "Une erreur est survenue.";
}

export const login = (password: string) =>
  request<{ ok: boolean }>("/auth/login", { method: "POST", body: JSON.stringify({ password }) });
export const logout = () => request<{ ok: boolean }>("/auth/logout", { method: "POST" });

export function sendChat(messages: Pick<Message, "role" | "content" | "context">[]) {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({
      messages: messages.map(({ role, content, context }) => ({
        role,
        content: context ? `${content}\n\n${context}` : content,
      })),
    }),
  });
}

export const approveAction = (id: string) =>
  request<PendingAction>(`/actions/${id}/approve`, { method: "POST" });
export const rejectAction = (id: string) =>
  request<PendingAction>(`/actions/${id}/reject`, { method: "POST" });

export type KnowledgeDocument = {
  id: string; filename: string; kind: string; size_bytes: number; chunk_count: number; created_at: string;
};
export const listDocuments = () => request<KnowledgeDocument[]>("/documents");
export const uploadDocument = (file: File) => {
  const body = new FormData();
  body.append("file", file);
  return request<KnowledgeDocument>("/documents", { method: "POST", body });
};
export const addNote = (title: string, text: string) =>
  request<KnowledgeDocument>("/documents/note", { method: "POST", body: JSON.stringify({ title, text }) });
export const deleteDocument = (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" });
