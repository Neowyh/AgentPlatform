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
        "mx-auto flex w-full flex-col items-center justify-center gap-2 px-8 py-4 text-center",
        className,
      )}
    >
      <div className="[font-family:var(--font-display),var(--font-sans)] text-2xl font-bold tracking-[-0.04em]">
        {isSkillMode ? (
          `✨ ${t.welcome.createYourOwnSkill} ✨`
        ) : (
          <>
            <span className="text-foreground">iDeer</span>
            <span className="font-semibold" style={{ color: "#2E4B3E" }}>
              ，实现你的idea
            </span>
          </>
        )}
      </div>
      {isSkillMode ? (
        <div className="text-muted-foreground text-sm">
          {t.welcome.createYourOwnSkillDescription.includes("\n") ? (
            <pre className="font-sans whitespace-pre">
              {t.welcome.createYourOwnSkillDescription}
            </pre>
          ) : (
            <p>{t.welcome.createYourOwnSkillDescription}</p>
          )}
        </div>
      ) : (
        <p className="text-muted-foreground max-w-[520px] text-[13px] leading-6">
          把一句话种进森林 — 对话留下
          <span className="font-semibold" style={{ color: "#2E4B3E" }}>
            踪迹
          </span>
          ，待办与产物在
          <span className="font-semibold" style={{ color: "#2E4B3E" }}>
            冷纸
          </span>
          上成形
        </p>
      )}
    </div>
  );
}
