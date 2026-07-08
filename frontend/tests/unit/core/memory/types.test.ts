import { describe, expect, it } from "vitest";

import type {
  MemoryFact,
  MemoryFactInput,
  MemoryFactPatchInput,
  UserMemory,
} from "@/core/memory/types";

describe("MemoryFact", () => {
  it("can be constructed with all fields", () => {
    const fact: MemoryFact = {
      id: "fact-1",
      content: "User prefers dark mode",
      category: "preference",
      confidence: 0.9,
      createdAt: "2024-01-01T00:00:00Z",
      source: "conversation",
    };
    expect(fact.id).toBe("fact-1");
    expect(fact.content).toBe("User prefers dark mode");
    expect(fact.confidence).toBe(0.9);
  });

  it("handles nullable sourceError", () => {
    const withError: MemoryFact = {
      id: "fact-2",
      content: "Test",
      category: "test",
      confidence: 0.5,
      createdAt: "2024-01-01T00:00:00Z",
      source: "import",
      sourceError: "Failed to verify",
    };
    const withoutError: MemoryFact = {
      id: "fact-3",
      content: "Test",
      category: "test",
      confidence: 0.5,
      createdAt: "2024-01-01T00:00:00Z",
      source: "import",
      sourceError: null,
    };
    expect(withError.sourceError).toBe("Failed to verify");
    expect(withoutError.sourceError).toBeNull();
  });
});

describe("MemoryFactInput", () => {
  it("can be constructed with all fields", () => {
    const input: MemoryFactInput = {
      content: "User likes cats",
      category: "preference",
      confidence: 0.8,
    };
    expect(input.content).toBe("User likes cats");
    expect(input.confidence).toBe(0.8);
  });
});

describe("MemoryFactPatchInput", () => {
  it("can be constructed with partial fields", () => {
    const patch: MemoryFactPatchInput = { content: "Updated content" };
    expect(patch.content).toBe("Updated content");
    expect(patch.category).toBeUndefined();
    expect(patch.confidence).toBeUndefined();
  });

  it("can be constructed with all fields", () => {
    const patch: MemoryFactPatchInput = {
      content: "Updated",
      category: "updated-category",
      confidence: 0.95,
    };
    expect(patch.confidence).toBe(0.95);
  });
});

describe("UserMemory", () => {
  it("can be constructed with the full nested structure", () => {
    const memory: UserMemory = {
      version: "1.0",
      lastUpdated: "2024-01-01T00:00:00Z",
      user: {
        workContext: {
          summary: "Software engineer",
          updatedAt: "2024-01-01T00:00:00Z",
        },
        personalContext: {
          summary: "Lives in NYC",
          updatedAt: "2024-01-01T00:00:00Z",
        },
        topOfMind: {
          summary: "Working on project X",
          updatedAt: "2024-01-01T00:00:00Z",
        },
      },
      history: {
        recentMonths: {
          summary: "Shipped feature Y",
          updatedAt: "2024-01-01T00:00:00Z",
        },
        earlierContext: {
          summary: "Joined company",
          updatedAt: "2023-06-01T00:00:00Z",
        },
        longTermBackground: {
          summary: "10 years experience",
          updatedAt: "2023-01-01T00:00:00Z",
        },
      },
      facts: [
        {
          id: "fact-1",
          content: "Uses Vim",
          category: "preference",
          confidence: 0.9,
          createdAt: "2024-01-01T00:00:00Z",
          source: "conversation",
        },
      ],
    };
    expect(memory.version).toBe("1.0");
    expect(memory.user.workContext.summary).toBe("Software engineer");
    expect(memory.history.recentMonths.summary).toBe("Shipped feature Y");
    expect(memory.facts).toHaveLength(1);
    const fact = memory.facts[0];
    expect(fact).toBeDefined();
    expect(fact!.content).toBe("Uses Vim");
  });
});
