"use client";

export interface Document {
  id: string;
  name: string;
  status: "ready" | "processing";
  created_at: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  document_count: number;
}

export function useDocuments() {
  // TODO: Replace with actual API call to RAGFlow
  const documents: Document[] = [
    {
      id: "doc-1",
      name: "Document 1",
      status: "ready",
      created_at: "2024-01-01",
    },
    {
      id: "doc-2",
      name: "Document 2",
      status: "processing",
      created_at: "2024-01-02",
    },
  ];

  return {
    documents,
    isLoading: false,
  };
}

export function useKnowledgeBases() {
  // TODO: Replace with actual API call to RAGFlow
  const knowledgeBases: KnowledgeBase[] = [
    {
      id: "kb-1",
      name: "Knowledge Base 1",
      description: "First knowledge base",
      document_count: 10,
    },
    {
      id: "kb-2",
      name: "Knowledge Base 2",
      description: "Second knowledge base",
      document_count: 5,
    },
  ];

  return {
    knowledgeBases,
    isLoading: false,
  };
}
