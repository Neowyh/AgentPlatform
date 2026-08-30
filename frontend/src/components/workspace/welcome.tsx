"use client";

import { useSearchParams } from "next/navigation";

import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

export function Welcome({
  className,
  mode: _mode,
}: {
  className?: string;
  mode?: "ultra" | "pro" | "thinking" | "flash";
}) {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const isSkillMode = searchParams.get("mode") === "skill";
  return (
    <div
      className={cn(
        "workbench-welcome mx-auto flex w-full flex-col items-center justify-center gap-2 px-8 py-4 text-center",
        className,
      )}
    >
      <div className="workbench-welcome-title font-bold tracking-[-0.04em]">
        {isSkillMode
          ? `✨ ${t.welcome.createYourOwnSkill} ✨`
          : t.welcome.greeting}
      </div>
      {isSkillMode ? (
        <div className="text-muted-foreground text-base">
          {t.welcome.createYourOwnSkillDescription.includes("\n") ? (
            <pre className="font-sans whitespace-pre">
              {t.welcome.createYourOwnSkillDescription}
            </pre>
          ) : (
            <p>{t.welcome.createYourOwnSkillDescription}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
