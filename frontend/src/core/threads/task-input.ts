import type { AgentThreadContext } from "./types";

export type TaskInputMessage = {
  text: string;
  files: unknown[];
};

export type TaskSubmission = {
  message: TaskInputMessage;
  context: Omit<
    AgentThreadContext,
    "thread_id" | "is_plan_mode" | "thinking_enabled" | "subagent_enabled"
  > & {
    mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
    reasoning_effort?: "minimal" | "low" | "medium" | "high";
  };
  skillName: string | null;
};

export type TaskInputInsertion =
  | { kind: "insert"; text: string }
  | { kind: "conflict"; current: string; incoming: string };

export function parseTaskSkillPrefix(
  text: string,
): { skillName: string; rest: string } | null {
  const match = /^\/([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?:\s+(.*))?$/.exec(text);
  if (!match) return null;
  return { skillName: match[1]!, rest: match[2] ?? "" };
}

export function prepareTaskSubmission<T extends TaskInputMessage>(
  message: T,
  context: TaskSubmission["context"],
): Omit<TaskSubmission, "message"> & {
  message: Omit<T, "text"> & { text: string };
} {
  const parsed = parseTaskSkillPrefix(message.text);
  const skillName = parsed?.skillName ?? null;
  return {
    message: {
      ...message,
      text: parsed ? parsed.rest : message.text,
    },
    context: skillName ? { ...context, skill_name: skillName } : context,
    skillName,
  };
}

export function hasTaskInput(message: TaskInputMessage): boolean {
  return message.text.trim().length > 0 || message.files.length > 0;
}

export function prepareTaskInputInsertion(
  current: string,
  incoming: string,
): TaskInputInsertion {
  return current.trim().length === 0
    ? { kind: "insert", text: incoming }
    : { kind: "conflict", current, incoming };
}

export function applyTaskInputInsertion(
  current: string,
  incoming: string,
  decision: "replace" | "append",
): string {
  return decision === "append" && current.trim().length > 0
    ? `${current}\n${incoming}`
    : incoming;
}

export function getResolvedInputMode(
  mode: TaskSubmission["context"]["mode"],
  supportsThinking: boolean,
): NonNullable<TaskSubmission["context"]["mode"]> {
  if (!supportsThinking && mode !== "flash") return "flash";
  if (mode) return mode;
  return supportsThinking ? "pro" : "flash";
}
