import { redirect } from "next/navigation";

import { legacyRedirectTarget } from "@/app/workspace/agents/legacy-redirect";

// Agent creation lives in the capability center's expert tab (issue 03); old
// URLs keep working through this redirect.
export default async function NewAgentPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const search = await searchParams;
  redirect(legacyRedirectTarget("/workspace/capabilities/experts/new", search));
}
