import { extractError } from "@/core/api/errors";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { Device, DeviceSession, PairingChallenge } from "./types";

const devicesURL = () => `${getBackendBaseURL()}/api/devices`;

async function jsonOrThrow<T>(response: Response, message: string): Promise<T> {
  if (!response.ok) return extractError(response, message);
  return response.json() as Promise<T>;
}

export async function listDevices(): Promise<Device[]> {
  return jsonOrThrow<Device[]>(
    await fetch(devicesURL()),
    "Failed to list devices",
  );
}

export async function createDevicePairing(): Promise<PairingChallenge> {
  return jsonOrThrow<PairingChallenge>(
    await fetch(`${devicesURL()}/pairing`, { method: "POST" }),
    "Failed to create device pairing",
  );
}

export async function confirmDevicePairing(
  pairingId: string,
  code: string,
): Promise<Device> {
  return jsonOrThrow<Device>(
    await fetch(
      `${devicesURL()}/pairing/${encodeURIComponent(pairingId)}/confirm`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      },
    ),
    "Failed to confirm device pairing",
  );
}

export async function completeDeviceRegistration(
  deviceId: string,
  publicKey: string,
  claimToken: string,
): Promise<DeviceSession> {
  return jsonOrThrow<DeviceSession>(
    await fetch(`${devicesURL()}/register/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: deviceId,
        public_key: publicKey,
        claim_token: claimToken,
      }),
    }),
    "Failed to complete device registration",
  );
}

export async function revokeDevice(deviceId: string): Promise<Device> {
  return jsonOrThrow<Device>(
    await fetch(`${devicesURL()}/${encodeURIComponent(deviceId)}/revoke`, {
      method: "POST",
    }),
    "Failed to revoke device",
  );
}
