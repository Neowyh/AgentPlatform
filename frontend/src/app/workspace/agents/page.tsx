import { redirect } from "next/navigation";

import { legacyRedirectTarget } from "@/app/workspace/agents/legacy-redirect";

// The standalone Agents management page was merged into the capability
// center's expert tab (issue 03); old URLs keep working through this redirect.
export default async function AgentsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const search = await searchParams;
  redirect(legacyRedirectTarget("/workspace/capabilities/experts", search));
}
