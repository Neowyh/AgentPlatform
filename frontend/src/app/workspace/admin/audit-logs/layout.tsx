import { redirect } from "next/navigation";

import { getServerSideUser } from "@/core/auth/server";
import { assertNever } from "@/core/auth/types";

export default async function AuditLogsLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const result = await getServerSideUser();

  switch (result.tag) {
    case "authenticated":
      if (result.user.system_role === "super_admin") {
        return children;
      }
      redirect("/workspace");
    case "needs_setup":
    case "system_setup_required":
      redirect("/setup");
    case "unauthenticated":
      redirect("/login");
    case "gateway_unavailable":
      redirect("/workspace");
    case "config_error":
      throw new Error(result.message);
    default:
      assertNever(result);
  }
}
