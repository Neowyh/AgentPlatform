import { redirect } from "next/navigation";

// Agent creation lives in the capability center's expert tab (issue 03); old
// URLs keep working through this redirect.
export default function NewAgentPage() {
  redirect("/workspace/capabilities/experts/new");
}
