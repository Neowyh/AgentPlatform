"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function SkillApplicationsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/workspace/admin/visibility-applications");
  }, [router]);

  return (
    <div className="flex size-full items-center justify-center">
      <p className="text-muted-foreground text-base">
        正在跳转到统一审批中心...
      </p>
    </div>
  );
}
