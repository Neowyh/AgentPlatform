import { redirect } from "next/navigation";

import { legacyRedirectTarget } from "@/app/workspace/agents/legacy-redirect";

// ADR-0007: canonical agent surfaces live at /workspace/agents.
export default async function ExpertChatRedirect({
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
      `/workspace/agents/${agent_name}/chats/${thread_id}`,
      search,
    ),
  );
}
