import { redirect } from "next/navigation";

import { legacyRedirectTarget } from "@/app/workspace/agents/legacy-redirect";

// ADR-0007: the agents gallery stays in the capability center (tab
// `agents`); the bare /workspace/agents URL keeps working through this
// redirect with query preserved.
export default async function AgentsGalleryRedirect({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const search = await searchParams;
  redirect(legacyRedirectTarget("/workspace/capabilities/agents", search));
}
