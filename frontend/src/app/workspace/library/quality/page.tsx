import { Suspense } from "react";

import { KnowledgeQualityPanel } from "@/components/workspace/library/knowledge-quality-panel";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";

export default function LibraryQualityPage() {
  return (
    <div className="flex size-full flex-col">
      <WorkspaceBreadcrumb />
      <Suspense>
        <KnowledgeQualityPanel />
      </Suspense>
    </div>
  );
}
