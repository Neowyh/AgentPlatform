"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  confirmDevicePairing,
  createDevicePairing,
  listDevices,
  revokeDevice,
} from "@/core/devices/api";
import type { Device, PairingChallenge } from "@/core/devices/types";
import { useI18n } from "@/core/i18n/hooks";

const statusVariant: Record<
  Device["status"],
  "default" | "secondary" | "destructive" | "outline"
> = {
  pending: "secondary",
  online: "default",
  offline: "outline",
  revoked: "destructive",
  blocked: "destructive",
  outdated: "secondary",
};

export default function DevicesPage() {
  const { t } = useI18n();
  const [devices, setDevices] = useState<Device[]>([]);
  const [pairing, setPairing] = useState<PairingChallenge | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setDevices(await listDevices());
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.admin.devices.error,
      );
    } finally {
      setLoading(false);
    }
  }, [t.admin.devices.error]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createPairing = async () => {
    setBusy(true);
    try {
      setPairing(await createDevicePairing());
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.admin.devices.error,
      );
    } finally {
      setBusy(false);
    }
  };

  const confirmPairing = async () => {
    if (!pairing) return;
    setConfirming(true);
    try {
      await confirmDevicePairing(pairing.pairing_id, pairing.code);
      toast.success(t.admin.devices.confirmPairing);
      setPairing(null);
      await refresh();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.admin.devices.error,
      );
    } finally {
      setConfirming(false);
    }
  };

  const revoke = async (device: Device) => {
    if (!window.confirm(t.admin.devices.revokeConfirm)) return;
    try {
      await revokeDevice(device.id);
      toast.success(t.admin.devices.revoked);
      await refresh();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.admin.devices.error,
      );
    }
  };

  const statusLabels: Record<Device["status"], string> = {
    pending: t.admin.devices.pending,
    online: t.admin.devices.online,
    offline: t.admin.devices.offline,
    revoked: t.admin.devices.revoked,
    blocked: t.admin.devices.blocked,
    outdated: t.admin.devices.outdated,
  };

  return (
    <div className="flex size-full flex-col" data-testid="devices-page">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="type-page-title font-semibold">
            {t.admin.devices.pageTitle}
          </h1>
          <p className="text-muted-foreground type-body mt-0.5">
            {t.admin.devices.pageDescription}
          </p>
        </div>
        <Button onClick={() => void createPairing()} disabled={busy}>
          {busy ? t.admin.devices.loading : t.admin.devices.createPairing}
        </Button>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {pairing && (
          <Card>
            <CardHeader>
              <CardTitle>
                {t.admin.devices.pairingCode}: {pairing.code}
              </CardTitle>
              <CardDescription>
                {t.admin.devices.pairingInstructions}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-end gap-3">
              <div className="min-w-64 space-y-2">
                <Label htmlFor="device-pairing-code">
                  {t.admin.devices.pairingCode}
                </Label>
                <Input id="device-pairing-code" value={pairing.code} readOnly />
              </div>
              <Button
                onClick={() => void confirmPairing()}
                disabled={confirming}
              >
                {confirming
                  ? t.admin.devices.confirming
                  : t.admin.devices.confirmPairing}
              </Button>
            </CardContent>
          </Card>
        )}

        {loading ? (
          <div className="text-muted-foreground type-body">
            {t.admin.devices.loading}
          </div>
        ) : devices.length === 0 ? (
          <div className="text-muted-foreground type-body">
            {t.admin.devices.empty}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {devices.map((device) => (
              <Card key={device.id}>
                <CardHeader className="flex flex-row items-start justify-between gap-4">
                  <div>
                    <CardTitle>{device.name}</CardTitle>
                    <CardDescription>{device.id}</CardDescription>
                  </div>
                  <Badge variant={statusVariant[device.status]}>
                    {statusLabels[device.status]}
                  </Badge>
                </CardHeader>
                <CardContent className="type-supporting space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <span className="text-muted-foreground">
                      {t.admin.devices.runtime}
                    </span>
                    <span>{device.runtime_version}</span>
                    <span className="text-muted-foreground">
                      {t.admin.devices.protocol}
                    </span>
                    <span>{device.protocol_version}</span>
                    <span className="text-muted-foreground">
                      {t.admin.devices.capabilities}
                    </span>
                    <span>{device.capabilities.join(", ") || "—"}</span>
                    <span className="text-muted-foreground">
                      {t.admin.devices.lastSeen}
                    </span>
                    <span>
                      {device.last_seen
                        ? new Date(device.last_seen).toLocaleString()
                        : t.admin.devices.never}
                    </span>
                  </div>
                  {device.status !== "revoked" && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => void revoke(device)}
                    >
                      {t.admin.devices.revoke}
                    </Button>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
