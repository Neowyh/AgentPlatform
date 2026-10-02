import { redirect } from "next/navigation";

// ADR-0007: canonical agent surfaces live at /workspace/agents.
export default async function ExpertEditRedirect({
  params,
}: {
  params: Promise<{ agent_name: string }>;
}) {
  const { agent_name } = await params;
  redirect(`/workspace/agents/${agent_name}/edit`);
}
