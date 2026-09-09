import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/core/api/fetcher", () => ({
  fetch: vi.fn(),
}));

vi.mock("@/core/config", () => ({
  getBackendBaseURL: vi.fn(() => "http://localhost:8000"),
}));

vi.mock("@/core/api/errors", () => ({
  extractError: vi.fn((_res: Response, msg: string) => {
    throw new Error(msg);
  }),
}));

import { fetch } from "@/core/api/fetcher";
import {
  completeDeviceRegistration,
  confirmDevicePairing,
  createDevicePairing,
  listDevices,
  revokeDevice,
} from "@/core/devices/api";

const mockFetch = vi.mocked(fetch);

function okJson(data: unknown): Response {
  return { ok: true, json: async () => data } as unknown as Response;
}

describe("devices API", () => {
  afterEach(() => vi.clearAllMocks());

  test("creates a pairing challenge", async () => {
    const payload = {
      pairing_id: "p1",
      code: "ABCDEFGH",
      pairing_url: "/pair",
      expires_at: "now",
    };
    mockFetch.mockResolvedValue(okJson(payload));

    await expect(createDevicePairing()).resolves.toEqual(payload);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/devices/pairing",
      { method: "POST" },
    );
  });

  test("confirms a pairing and completes registration separately", async () => {
    mockFetch
      .mockResolvedValueOnce(okJson({ id: "d1", status: "pending" }))
      .mockResolvedValueOnce(
        okJson({ session_id: "s1", session_token: "secret" }),
      );

    await confirmDevicePairing("p1", "ABCDEFGH");
    await completeDeviceRegistration("d1", "public-key", "claim-token");

    expect(mockFetch.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/api/devices/pairing/p1/confirm",
    );
    expect(mockFetch.mock.calls[1]?.[0]).toBe(
      "http://localhost:8000/api/devices/register/complete",
    );
  });

  test("lists and revokes devices", async () => {
    mockFetch
      .mockResolvedValueOnce(okJson([]))
      .mockResolvedValueOnce(okJson({ id: "d1", status: "revoked" }));

    await listDevices();
    await revokeDevice("d1");

    expect(mockFetch.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/api/devices",
    );
    expect(mockFetch.mock.calls[1]?.[1]).toEqual({ method: "POST" });
  });
});
