import { redirect } from "next/navigation";

// ADR-0007: canonical agent surfaces live at /workspace/agents.
export default function NewExpertRedirect() {
  redirect("/workspace/agents/new");
}
