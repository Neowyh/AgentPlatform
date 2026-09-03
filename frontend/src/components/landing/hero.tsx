"use client";

import { ChevronRightIcon } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { FlickeringGrid } from "@/components/ui/flickering-grid";
import Galaxy from "@/components/ui/galaxy";
import { WordRotate } from "@/components/ui/word-rotate";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

export function Hero({ className }: { className?: string }) {
  const { t } = useI18n();

  return (
    <div
      className={cn(
        "flex size-full flex-col items-center justify-center",
        className,
      )}
    >
      <div className="absolute inset-0 z-0 bg-black/40">
        <Galaxy
          mouseRepulsion={false}
          starSpeed={0.2}
          density={0.6}
          glowIntensity={0.35}
          twinkleIntensity={0.3}
          speed={0.5}
        />
      </div>
      <FlickeringGrid
        className="mask-[url(/images/deer.svg)] mask-size-[100vw] mask-center mask-no-repeat md:mask-size-[72vh] absolute inset-0 z-0 translate-y-8"
        squareSize={4}
        gridGap={4}
        color={"white"}
        maxOpacity={0.3}
        flickerChance={0.25}
      />
      <div className="container-md relative z-10 mx-auto flex h-screen flex-col items-center justify-center">
        <h1 className="type-display-hero flex items-center gap-2 font-bold">
          <div>{t.landing.heroTitlePrefix}</div>{" "}
          <WordRotate words={t.landing.heroWords} />
        </h1>
        <p className="text-muted-foreground type-body text-shadow-sm mt-8 text-center">
          {t.landing.heroTagline}
        </p>
        <Link href="/workspace">
          <Button className="size-lg scale-108 mt-8" size="lg">
            <span className="type-body">{t.landing.heroCta}</span>
            <ChevronRightIcon className="size-4" />
          </Button>
        </Link>
      </div>
    </div>
  );
}
