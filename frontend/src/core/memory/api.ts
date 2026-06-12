import { extractError } from "../api/errors";
import { fetch } from "../api/fetcher";
import { getBackendBaseURL } from "../config";

import type {
  MemoryFactInput,
  MemoryFactPatchInput,
  UserMemory,
} from "./types";

export async function loadMemory(): Promise<UserMemory> {
  const response = await fetch(`${getBackendBaseURL()}/api/memory`);
  if (!response.ok) {
    await extractError(response, "Failed to fetch memory");
  }
  return response.json() as Promise<UserMemory>;
}

export async function clearMemory(): Promise<UserMemory> {
  const response = await fetch(`${getBackendBaseURL()}/api/memory`, {
    method: "DELETE",
  });
  if (!response.ok) {
    await extractError(response, "Failed to clear memory");
  }
  return response.json() as Promise<UserMemory>;
}

export async function deleteMemoryFact(factId: string): Promise<UserMemory> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/memory/facts/${encodeURIComponent(factId)}`,
    {
      method: "DELETE",
    },
  );
  if (!response.ok) {
    await extractError(response, "Failed to delete memory fact");
  }
  return response.json() as Promise<UserMemory>;
}

export async function exportMemory(): Promise<UserMemory> {
  const response = await fetch(`${getBackendBaseURL()}/api/memory/export`);
  if (!response.ok) {
    await extractError(response, "Failed to export memory");
  }
  return response.json() as Promise<UserMemory>;
}

export async function importMemory(memory: UserMemory): Promise<UserMemory> {
  const response = await fetch(`${getBackendBaseURL()}/api/memory/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(memory),
  });
  if (!response.ok) {
    await extractError(response, "Failed to import memory");
  }
  return response.json() as Promise<UserMemory>;
}

export async function createMemoryFact(
  input: MemoryFactInput,
): Promise<UserMemory> {
  const response = await fetch(`${getBackendBaseURL()}/api/memory/facts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    await extractError(response, "Failed to create memory fact");
  }
  return response.json() as Promise<UserMemory>;
}

export async function updateMemoryFact(
  factId: string,
  input: MemoryFactPatchInput,
): Promise<UserMemory> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/memory/facts/${encodeURIComponent(factId)}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(input),
    },
  );
  if (!response.ok) {
    await extractError(response, "Failed to update memory fact");
  }
  return response.json() as Promise<UserMemory>;
}
