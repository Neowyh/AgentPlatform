export type DeviceStatus =
  | "pending"
  | "online"
  | "offline"
  | "revoked"
  | "blocked"
  | "outdated";

export interface Device {
  id: string;
  owner_id: string;
  name: string;
  status: DeviceStatus;
  protocol_version: string;
  runtime_version: string;
  capabilities: string[];
  policy_hash: string | null;
  last_seen: string | null;
  created_at: string;
}

export interface PairingChallenge {
  pairing_id: string;
  code: string;
  pairing_url: string;
  expires_at: string;
}

export interface DeviceClaim {
  device: Device;
  pairing_id: string;
  claim_token: string;
  claim_expires_at: string;
}

export interface DeviceSession {
  device: Device;
  session_id: string;
  session_token: string;
  session_expires_at: string;
}
