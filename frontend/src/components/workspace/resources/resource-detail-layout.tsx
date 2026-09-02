import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { WorkspaceBreadcrumb } from "@/components/workspace/workspace-breadcrumb";

interface ResourceDetailLayoutProps {
  backHref: string;
  breadcrumb: ReactNode;
  icon: ReactNode;
  title: string;
  description?: string | null;
  actions: ReactNode;
  children: ReactNode;
}

export function ResourceDetailLayout({
  backHref,
  breadcrumb,
  icon,
  title,
  description,
  actions,
  children,
}: ResourceDetailLayoutProps) {
  return (
    <div className="flex size-full flex-col">
      {breadcrumb ?? <WorkspaceBreadcrumb />}
      <header className="border-border/80 border-b px-4 py-4 sm:px-6 sm:py-5">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <Button
              variant="ghost"
              size="icon-sm"
              className="mt-1 shrink-0"
              asChild
            >
              <Link href={backHref} aria-label={title}>
                <span aria-hidden="true">←</span>
              </Link>
            </Button>
            <div className="bg-primary/10 text-primary mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
              {icon}
            </div>
            <div className="min-w-0">
              <h1 className="type-page-title truncate font-semibold">
                {title}
              </h1>
              {description && (
                <p className="text-muted-foreground type-body mt-1 line-clamp-3 max-w-3xl">
                  {description}
                </p>
              )}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2 lg:max-w-[48%] lg:justify-end">
            {actions}
          </div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-5 sm:p-6">
        <div className="mx-auto grid max-w-4xl gap-5">{children}</div>
      </div>
    </div>
  );
}

export function ResourceDetailCard({
  title,
  description,
  children,
  className = "",
}: {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`bg-card rounded-2xl border p-5 shadow-sm sm:p-6 ${className}`}
    >
      <div className="mb-5">
        <h2 className="type-section-title font-semibold">{title}</h2>
        {description && (
          <p className="text-muted-foreground type-body mt-1">{description}</p>
        )}
      </div>
      {children}
    </section>
  );
}

export function ResourceDetailRow({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="border-border/70 flex flex-col gap-1 border-b py-3 last:border-b-0">
      <dt className="text-muted-foreground type-caption">{label}</dt>
      <dd className="type-body break-words">{value}</dd>
    </div>
  );
}
