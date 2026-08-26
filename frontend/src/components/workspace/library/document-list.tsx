"use client";

import { useDocuments } from "@/core/library";

export function DocumentList() {
  const { documents, isLoading } = useDocuments();

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  if (!documents || documents.length === 0) {
    return <div className="text-muted-foreground">No documents found</div>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {documents.map((doc) => (
        <div key={doc.id} className="rounded-lg border p-4">
          <h3 className="font-medium">{doc.name}</h3>
          <p className="text-muted-foreground text-sm">{doc.id}</p>
          <div className="mt-2 flex items-center justify-between">
            <span
              className={`rounded-full px-2 py-1 text-xs ${
                doc.status === "ready"
                  ? "bg-green-100 text-green-800"
                  : "bg-yellow-100 text-yellow-800"
              }`}
            >
              {doc.status}
            </span>
            <span className="text-muted-foreground text-xs">
              {doc.created_at}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
