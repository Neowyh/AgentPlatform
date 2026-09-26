import { redirect } from "next/navigation";

import { legacyRedirectTarget } from "@/app/workspace/agents/legacy-redirect";

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
  redirect(
    legacyRedirectTarget(
      `/workspace/capabilities/experts/${encodeURIComponent(agent_name)}/chats/${encodeURIComponent(thread_id)}`,
      search,
    ),
  );
}
