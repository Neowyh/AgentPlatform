export type { CreateKnowledgeBaseRequest, KnowledgeBase } from "./api";
export { createKnowledgeBase, listKnowledgeBases } from "./api";
export { useCreateKnowledgeBase, useKnowledgeBases } from "./hooks";

export interface Document {
  id: string;
  name: string;
  status: "ready" | "processing";
  created_at: string;
}

export function useDocuments() {
  return {
    documents: [
      {
        id: "doc-1",
        name: "Document 1",
        status: "ready" as const,
        created_at: "2024-01-01",
      },
      {
        id: "doc-2",
        name: "Document 2",
        status: "processing" as const,
        created_at: "2024-01-02",
      },
    ],
    isLoading: false,
  };
}
