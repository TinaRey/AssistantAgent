export type ToolStatus =
  | "ok" | "error" | "timeout" | "invalid_input" | "unknown_tool" | "pending_approval";

export type ToolTrace = {
  id: string; call_id: string; tool: string; status: ToolStatus; duration_ms: number; error: string | null;
};
export type Artifact = { call_id: string; tool: string; data: Record<string, any> };
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
  error?: boolean;
  traces?: ToolTrace[];
  artifacts?: Artifact[];
  pending?: PendingAction[];
};

export type Conversation = { id: string; title: string; messages: Message[]; updatedAt: number };
