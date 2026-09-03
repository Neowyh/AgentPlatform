"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useI18n } from "@/core/i18n/hooks";

export default function SkillApplicationsPage() {
  const router = useRouter();
  const { t } = useI18n();

  useEffect(() => {
    router.replace("/workspace/admin/visibility-applications");
  }, [router]);

  return (
    <div className="flex size-full items-center justify-center">
      <p className="text-muted-foreground type-body">
        {t.admin.skillApplications.redirecting()}
      </p>
    </div>
  );
}
