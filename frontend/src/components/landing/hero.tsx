"use client";

import { ChevronRightIcon } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { WordRotate } from "@/components/ui/word-rotate";
import { useI18n } from "@/core/i18n/hooks";
import { isStaticWebsiteOnly } from "@/core/static-mode";
import { cn } from "@/lib/utils";

export function Hero({ className }: { className?: string }) {
  const { t } = useI18n();
  const ctaHref = isStaticWebsiteOnly()
    ? "/workspace"
    : "/login?next=%2Fworkspace";

  return (
    <div
      className={cn(
        "flex size-full flex-col items-center justify-center",
        className,
      )}
    >
      <div className="absolute inset-0 z-0 bg-[#f8f1e5]" />
      <div className="absolute inset-0 z-0 bg-[#8a6a4a]/8 mask-[url(/images/deer.svg)] mask-size-[100vw] mask-center mask-no-repeat md:mask-size-[72vh]" />
      <div className="container-md relative z-10 mx-auto flex h-screen flex-col items-center justify-center">
        <h1 className="type-display-hero flex items-center gap-2 text-center font-bold text-[#3d2b1f]">
          <div>{t.landing.heroTitlePrefix}</div>{" "}
          <WordRotate words={t.landing.heroWords} />
        </h1>
        <p className="mt-8 text-center text-xl text-[#6b4c32] md:text-2xl">
          {t.landing.heroTagline}
        </p>
        <Link href={ctaHref}>
          <Button
            className="mt-8 min-h-12 bg-[#7a5132] px-6 text-white hover:bg-[#623f27] focus-visible:ring-[#7a5132]"
            size="lg"
          >
            <span className="type-body">{t.landing.heroCta}</span>
            <ChevronRightIcon className="size-4" />
          </Button>
        </Link>
      </div>
    </div>
  );
}
