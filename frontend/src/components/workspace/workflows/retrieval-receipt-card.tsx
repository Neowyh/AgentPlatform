"use client";

interface RetrievalItem {
  display_name?: string | null;
  content?: string | null;
  score?: number | null;
  position?: Record<string, unknown>;
}

interface RetrievalReceipt {
  receipt_id?: string;
  knowledge_base_id?: string;
  revision_no?: number | null;
  manifest_hash?: string | null;
  configuration_source?: string | null;
  result_status?: string;
  items?: RetrievalItem[];
  returned_count?: number;
  truncated?: boolean;
}

function extractReceipts(
  snapshot?: Record<string, unknown>,
): RetrievalReceipt[] {
  const evidence = snapshot?.run_evidence;
  if (!evidence || typeof evidence !== "object") return [];
  const receipts = (evidence as Record<string, unknown>).retrieval_receipts;
  if (!Array.isArray(receipts)) return [];
  return receipts.filter(
    (receipt): receipt is RetrievalReceipt =>
      typeof receipt === "object" && receipt !== null,
  );
}

function location(item: RetrievalItem): string | null {
  const position = item.position;
  if (!position || typeof position !== "object") return null;
  const page = position.page ?? position.page_number;
  if (typeof page === "string" || typeof page === "number") {
    return `Page ${page}`;
  }
  if (typeof position.section === "string") return position.section;
  return null;
}

export function RetrievalReceiptCard({
  snapshot,
  loading = false,
  error,
}: {
  snapshot?: Record<string, unknown>;
  loading?: boolean;
  error?: string | null;
}) {
  if (loading) {
    return (
      <section
        className="rounded-lg border p-4"
        data-testid="retrieval-receipts-loading"
      >
        <p className="type-body text-muted-foreground">
          Loading retrieval evidence…
        </p>
      </section>
    );
  }
  if (error) {
    return (
      <section
        className="rounded-lg border p-4"
        data-testid="retrieval-receipts-error"
      >
        <p className="type-body text-destructive">{error}</p>
      </section>
    );
  }
  const receipts = extractReceipts(snapshot);
  if (receipts.length === 0) return null;

  return (
    <section className="rounded-lg border p-4" data-testid="retrieval-receipts">
      <h2 className="type-section-title font-medium">Retrieval evidence</h2>
      <div className="mt-3 space-y-4">
        {receipts.map((receipt) => (
          <article
            key={
              receipt.receipt_id ??
              `${receipt.knowledge_base_id}-${receipt.revision_no}`
            }
          >
            <p className="type-body text-muted-foreground">
              KB {receipt.knowledge_base_id?.slice(0, 8) ?? "?"} · v
              {receipt.revision_no ?? "?"} ·{" "}
              {receipt.result_status ?? "unknown"}
              {receipt.configuration_source
                ? ` · ${receipt.configuration_source}`
                : ""}
              {receipt.truncated ? " · results truncated" : ""}
            </p>
            {receipt.items?.length ? (
              <ul className="mt-2 space-y-2">
                {receipt.items.map((item, index) => (
                  <li
                    key={`${receipt.receipt_id ?? "receipt"}-${index}`}
                    className="rounded border p-2"
                  >
                    <p className="type-body font-medium">
                      {item.display_name ?? "Unnamed document"}
                      {location(item) ? ` · ${location(item)}` : ""}
                      {typeof item.score === "number"
                        ? ` · retrieval score ${item.score}`
                        : ""}
                    </p>
                    {item.content ? (
                      <p className="type-body text-muted-foreground mt-1 break-words whitespace-pre-wrap">
                        {item.content}
                      </p>
                    ) : (
                      <p className="type-body text-muted-foreground mt-1">
                        Snippet unavailable
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="type-body text-muted-foreground mt-2">
                No matching content.
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
