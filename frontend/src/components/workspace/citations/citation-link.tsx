import { ExternalLinkIcon } from "lucide-react";
import { isValidElement, type ComponentProps, type ReactNode } from "react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { cn } from "@/lib/utils";

type EvidenceItem = {
  display_name?: string | null;
  content?: string | null;
  position?: Record<string, unknown>;
  score?: number | null;
};

/** Extract visible text from renderer-provided ReactNode children. */
export function extractReactNodeText(node: ReactNode): string | null {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }
  if (Array.isArray(node)) {
    const text = node
      .map(extractReactNodeText)
      .filter((value): value is string => value !== null)
      .join("");
    return text || null;
  }
  if (isValidElement(node)) {
    const children = (node.props as { children?: ReactNode }).children;
    return children === undefined ? null : extractReactNodeText(children);
  }
  return null;
}

export function CitationLink({
  href,
  children,
  runId,
  className,
  ...props
}: ComponentProps<"a"> & { runId?: string }) {
  if (href?.startsWith("evidence://")) {
    return (
      <EvidenceCitationLink href={href} runId={runId} className={className}>
        {children}
      </EvidenceCitationLink>
    );
  }
  const domain = extractDomain(href ?? "");

  // Priority: children > domain
  const childrenText =
    extractReactNodeText(children)?.replace(/^citation:\s*/i, "") ?? null;
  const isGenericText = childrenText === "Source" || childrenText === "来源";
  const displayText = (!isGenericText && childrenText) ?? domain;

  return (
    <HoverCard closeDelay={0} openDelay={0}>
      <HoverCardTrigger asChild>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className={cn("inline-flex items-center", className)}
          onClick={(e) => e.stopPropagation()}
          {...props}
        >
          <Badge
            variant="secondary"
            className="hover:bg-secondary/80 type-compact mx-0.5 cursor-pointer gap-1 rounded-full px-2 py-0.5 font-normal"
          >
            {displayText}
            <ExternalLinkIcon className="size-3" />
          </Badge>
        </a>
      </HoverCardTrigger>
      <HoverCardContent className={cn("relative w-80 p-0", className)}>
        <div className="p-3">
          <div className="space-y-1">
            {displayText && (
              <h4 className="type-supporting truncate leading-tight font-medium">
                {displayText}
              </h4>
            )}
            {href && (
              <p className="text-muted-foreground type-compact truncate break-all">
                {href}
              </p>
            )}
          </div>
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary type-compact mt-2 inline-flex items-center gap-1 hover:underline"
          >
            Visit source
            <ExternalLinkIcon className="size-3" />
          </a>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}

function EvidenceCitationLink({
  href,
  children,
  runId,
  className,
}: ComponentProps<"a"> & { runId?: string }) {
  const evidenceId = href?.slice("evidence://".length) ?? "";
  const label = extractReactNodeText(children) ?? "Knowledge evidence";
  const [open, setOpen] = useState(false);
  const [item, setItem] = useState<EvidenceItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !runId || !evidenceId) return;
    let cancelled = false;
    setItem(null);
    setError(null);
    void fetch(
      `${getBackendBaseURL()}/api/runs/${encodeURIComponent(runId)}/evidence`,
    )
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (await response.json()) as {
          receipts?: Array<Record<string, unknown>>;
        };
      })
      .then((payload) => {
        if (cancelled) return;
        for (const receipt of payload.receipts ?? []) {
          const items = Array.isArray(receipt.items) ? receipt.items : [];
          const found = items.find(
            (candidate): candidate is EvidenceItem =>
              typeof candidate === "object" &&
              candidate !== null &&
              (candidate as Record<string, unknown>).evidence_id === evidenceId,
          );
          if (found) {
            setItem(found);
            return;
          }
        }
        setError("This knowledge evidence is unavailable.");
      })
      .catch(() => {
        if (!cancelled) setError("This knowledge evidence is unavailable.");
      });
    return () => {
      cancelled = true;
    };
  }, [evidenceId, open, runId]);

  return (
    <>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          if (runId) setOpen(true);
        }}
        disabled={!runId}
        aria-label={runId ? `Open ${label}` : `${label} unavailable`}
        className={cn(
          "text-primary mx-0.5 inline-flex items-center underline underline-offset-2",
          className,
        )}
      >
        {label}
        <ExternalLinkIcon className="ml-1 size-3" />
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="evidence-panel">
          <DialogHeader>
            <DialogTitle>{item?.display_name ?? label}</DialogTitle>
            <DialogDescription>
              {formatPosition(item?.position) ?? "Location unavailable"}
            </DialogDescription>
          </DialogHeader>
          {error ? (
            <p className="text-destructive type-body">{error}</p>
          ) : item ? (
            <div className="max-h-80 overflow-y-auto rounded border p-3">
              <p className="type-body whitespace-pre-wrap">
                {item.content ?? "Snippet unavailable"}
              </p>
              {typeof item.score === "number" && (
                <p className="text-muted-foreground type-compact mt-3">
                  Retrieval score: {item.score}
                </p>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground type-body">Loading evidence…</p>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function formatPosition(position?: Record<string, unknown>): string | null {
  if (!position) return null;
  const page = position.page ?? position.page_number;
  if (typeof page === "string" || typeof page === "number")
    return `Page ${page}`;
  return typeof position.section === "string" ? position.section : null;
}

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./i, "");
  } catch {
    return url;
  }
}
