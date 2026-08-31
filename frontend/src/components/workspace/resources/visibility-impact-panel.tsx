"use client";

import { useEffect, useState } from "react";

import { Switch } from "@/components/ui/switch";
import { useI18n } from "@/core/i18n/hooks";
import {
  getVisibilityImpact,
  type VisibilityImpact as VisibilityImpactData,
} from "@/core/resources/api";
import { classifyVisibilityChange } from "@/core/visibility-applications/options";

interface VisibilityImpactPanelProps {
  resourceId: string;
  currentVisibility: string;
  targetVisibility: string;
  scopeDepartmentId?: string | null;
  onCascadeChange?: (cascade: boolean) => void;
}

export function VisibilityImpactPanel({
  resourceId,
  currentVisibility,
  targetVisibility,
  scopeDepartmentId,
  onCascadeChange,
}: VisibilityImpactPanelProps) {
  const { t } = useI18n();
  const [impact, setImpact] = useState<VisibilityImpactData | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [cascade, setCascade] = useState(false);

  const isDowngrade =
    classifyVisibilityChange(currentVisibility, targetVisibility) ===
    "downgrade";

  useEffect(() => {
    if (!isDowngrade) {
      setImpact(null);
      setLoadFailed(false);
      setCascade(false);
      onCascadeChange?.(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadFailed(false);
    getVisibilityImpact({
      resource_id: resourceId,
      target_visibility: targetVisibility,
      scope_department_id: scopeDepartmentId,
    })
      .then((data) => {
        if (!cancelled) setImpact(data);
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resourceId, targetVisibility, isDowngrade]);

  if (!isDowngrade || loading || !impact) return null;

  const typeLabel = (type: string): string => {
    if (type === "agent") return t.resources.resourceTypeAgent;
    if (type === "skill") return t.resources.resourceTypeSkill;
    if (type === "workflow") return t.resources.resourceTypeWorkflow;
    if (type === "tool") return t.resources.resourceTypeTool;
    return type;
  };

  const visibilityLabel = (visibility: string): string => {
    if (visibility === "private") return t.resources.visibilityPrivate;
    if (visibility === "department") return t.resources.visibilityDepartment;
    if (visibility === "public") return t.resources.visibilityPublic;
    return visibility;
  };

  if (loadFailed) {
    return (
      <p className="text-destructive type-body">
        {t.resources.impactLoadError}
      </p>
    );
  }

  if (impact.total === 0) return null;

  const repairableCount = impact.impacted.filter(
    (item) => !item.blocked,
  ).length;

  return (
    <div className="type-body space-y-2 rounded-lg border border-amber-300/60 bg-amber-50 p-3 text-amber-950 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-100">
      <p className="font-medium">{t.resources.impactTitle}</p>
      <p>
        {t.resources.impactSummary(
          impact.total,
          impact.direct.length,
          impact.transitive.length,
        )}
      </p>
      {impact.blocked_count > 0 && (
        <p>{t.resources.impactBlockedSummary(impact.blocked_count)}</p>
      )}
      <ul className="type-body max-h-40 space-y-1 overflow-y-auto">
        {impact.impacted.map((item) => (
          <li key={item.resource_id} className="flex justify-between gap-3">
            <span className="min-w-0 truncate">
              {item.display_name || item.slug}
              <span className="ml-1 opacity-70">
                （{typeLabel(item.type)}）
              </span>
            </span>
            <span className="shrink-0 opacity-70">
              {visibilityLabel(item.current_visibility)} →{" "}
              {visibilityLabel(item.proposed_visibility)}
            </span>
          </li>
        ))}
      </ul>
      {repairableCount > 0 && (
        <label className="flex cursor-pointer items-center justify-between gap-2 pt-1">
          <span>{t.resources.impactCascadeLabel}</span>
          <Switch
            checked={cascade}
            onCheckedChange={(next) => {
              setCascade(next);
              onCascadeChange?.(next);
            }}
          />
        </label>
      )}
    </div>
  );
}
