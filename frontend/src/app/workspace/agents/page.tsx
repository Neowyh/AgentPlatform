import { redirect } from "next/navigation";

// The standalone Agents management page was merged into the capability
// center's expert tab (issue 03); old URLs keep working through this redirect.
export default function AgentsPage() {
  redirect("/workspace/capabilities/experts");
}
