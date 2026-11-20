import type { ChatResponse, Message, PendingAction } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
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

export function sendChat(messages: Pick<Message, "role" | "content">[]) {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ messages: messages.map(({ role, content }) => ({ role, content })) }),
  });
}

export const approveAction = (id: string) =>
  request<PendingAction>(`/actions/${id}/approve`, { method: "POST" });
export const rejectAction = (id: string) =>
  request<PendingAction>(`/actions/${id}/reject`, { method: "POST" });
