import { redirect } from "next/navigation";

// Expert chats live under the capability center (issue 03); old DeerFlow URLs
// keep working through this redirect. The query string is preserved so
// mock-mode deep links (?mock=true) survive the hop.
export default async function AgentChatRedirectPage({
  params,
  searchParams,
}: {
  params: Promise<{ agent_name: string; thread_id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { agent_name, thread_id } = await params;
  const search = await searchParams;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(search)) {
    if (typeof value === "string") {
      query.set(key, value);
    } else if (Array.isArray(value)) {
      for (const item of value) query.append(key, item);
    }
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  redirect(
    `/workspace/capabilities/experts/${encodeURIComponent(agent_name)}/chats/${encodeURIComponent(thread_id)}${suffix}`,
  );
}
