export type ToolStatus =
  | "ok" | "error" | "timeout" | "invalid_input" | "unknown_tool" | "pending_approval";

export type ToolTrace = {
  id: string; call_id: string; tool: string; status: ToolStatus; duration_ms: number; error: string | null;
};
export type Artifact = {
  call_id: string; tool: string; data: Record<string, any>;
  /** The user's own edits of a draft (email/post), kept in this browser. */
  edits?: Record<string, any>;
};
export type PendingAction = {
  id: string; tool: string; arguments: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "failed";
};

export type ChatResponse = {
  reply: string; tool_calls: ToolTrace[]; pending_actions: PendingAction[];
  artifacts: Artifact[]; iteration_limit_reached: boolean;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Sent to the assistant with the message but not displayed (e.g. the current draft). */
  context?: string;
  /** The user rewrote this assistant message by hand. */
  edited?: boolean;
  error?: boolean;
  traces?: ToolTrace[];
  artifacts?: Artifact[];
  pending?: PendingAction[];
};

export type Conversation = { id: string; title: string; messages: Message[]; updatedAt: number };

const TITLE_MAX = 200;

/** Full title from the first user message (the sidebar's CSS ellipsis does the visual truncation). */
export function conversationTitle(c: Conversation): string {
  const first = c.messages.find((m) => m.role === "user");
  if (!first) return "Nouvelle conversation";
  const text = first.content.replace(/\s+/g, " ").trim();
  return text.length > TITLE_MAX ? `${text.slice(0, TITLE_MAX)}…` : text;
}
