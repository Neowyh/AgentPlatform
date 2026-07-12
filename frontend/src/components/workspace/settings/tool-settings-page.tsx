"use client";

import { PenLineIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from "@/components/ui/item";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/core/i18n/hooks";
import {
  useAddMCPServer,
  useDeleteMCPServer,
  useEnableMCPServer,
  useMCPConfig,
  useUpdateMCPServer,
} from "@/core/mcp/hooks";
import type { MCPServerConfig } from "@/core/mcp/types";
import { env } from "@/env";

import { SettingsSection } from "./settings-section";

type MCPServerFormState = {
  name: string;
  type: "stdio" | "sse" | "http";
  command: string;
  args: string;
  url: string;
  env: Record<string, string>;
  headers: Record<string, string>;
  description: string;
  enabled: boolean;
};

const DEFAULT_MCP_FORM: MCPServerFormState = {
  name: "",
  type: "stdio",
  command: "",
  args: "",
  url: "",
  env: {},
  headers: {},
  description: "",
  enabled: true,
};

function buildFormFromConfig(
  name: string,
  config: MCPServerConfig,
): MCPServerFormState {
  return {
    name,
    type: config.type,
    command: config.command ?? "",
    args: (config.args ?? []).join("\n"),
    url: config.url ?? "",
    env: { ...config.env },
    headers: { ...config.headers },
    description: config.description,
    enabled: config.enabled,
  };
}

function buildConfigFromForm(form: MCPServerFormState): MCPServerConfig {
  return {
    enabled: form.enabled,
    type: form.type,
    command: form.type === "stdio" ? form.command : undefined,
    args: form.type === "stdio" ? form.args.split("\n").filter(Boolean) : [],
    env: form.env,
    url: form.type !== "stdio" ? form.url : undefined,
    headers: form.type !== "stdio" ? form.headers : {},
    description: form.description,
  };
}

function KeyValueEditor({
  value,
  onChange,
}: {
  value: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
}) {
  const entries = Object.entries(value);
  return (
    <div className="space-y-2">
      {entries.map(([key, val]) => (
        <div key={key} className="flex items-center gap-2">
          <Input value={key} readOnly className="flex-1" />
          <Input
            value={val}
            onChange={(e) => onChange({ ...value, [key]: e.target.value })}
            className="flex-1"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => {
              const next = { ...value };
              delete next[key];
              onChange(next);
            }}
          >
            <Trash2Icon className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => {
          let newKey = "key";
          let i = 0;
          while (newKey in value) {
            i++;
            newKey = `key_${i}`;
          }
          onChange({ ...value, [newKey]: "" });
        }}
      >
        <PlusIcon className="mr-1 h-3 w-3" />
        Add
      </Button>
    </div>
  );
}

function getMCPErrorMessage(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  if (msg.toLowerCase().includes("forbidden") || msg.includes("403")) {
    return "MCP configuration is managed by super administrators. Please contact your admin.";
  }
  return msg;
}

export function ToolSettingsPage() {
  const { t } = useI18n();
  const { config, isLoading, error } = useMCPConfig();
  const [formOpen, setFormOpen] = useState(false);
  const [editingServer, setEditingServer] = useState<string | null>(null);
  const [form, setForm] = useState<MCPServerFormState>(DEFAULT_MCP_FORM);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const addServer = useAddMCPServer();
  const updateServer = useUpdateMCPServer();
  const deleteServer = useDeleteMCPServer();
  const enableServer = useEnableMCPServer();

  function openAddForm() {
    setEditingServer(null);
    setForm(DEFAULT_MCP_FORM);
    setFormOpen(true);
  }

  function openEditForm(name: string, serverConfig: MCPServerConfig) {
    setEditingServer(name);
    setForm(buildFormFromConfig(name, serverConfig));
    setFormOpen(true);
  }

  function closeForm() {
    setFormOpen(false);
    setEditingServer(null);
    setForm(DEFAULT_MCP_FORM);
  }

  async function handleSave() {
    const trimmedName = form.name.trim();
    if (!trimmedName) {
      toast.error(t.settings.tools.validationNameRequired);
      return;
    }

    if (editingServer === null) {
      if (addServer.isPending || updateServer.isPending) return;
      try {
        await addServer.mutateAsync({
          name: trimmedName,
          serverConfig: buildConfigFromForm(form),
        });
        toast.success(t.settings.tools.addSuccess);
        closeForm();
      } catch (err) {
        toast.error(getMCPErrorMessage(err));
      }
    } else {
      if (updateServer.isPending) return;
      try {
        await updateServer.mutateAsync({
          name: editingServer,
          serverConfig: buildConfigFromForm(form),
        });
        toast.success(t.settings.tools.editSuccess);
        closeForm();
      } catch (err) {
        toast.error(getMCPErrorMessage(err));
      }
    }
  }

  async function handleDelete() {
    if (!deleteTarget || deleteServer.isPending) return;
    try {
      await deleteServer.mutateAsync({ name: deleteTarget });
      toast.success(t.settings.tools.deleteSuccess);
      setDeleteTarget(null);
    } catch (err) {
      toast.error(getMCPErrorMessage(err));
    }
  }

  const servers = config?.mcp_servers ?? {};
  const isFormPending = addServer.isPending || updateServer.isPending;

  return (
    <>
      <SettingsSection
        title={t.settings.tools.title}
        description={t.settings.tools.description}
      >
        {isLoading ? (
          <div className="text-muted-foreground text-sm">
            {t.common.loading}
          </div>
        ) : error ? (
          <div>Error: {error.message}</div>
        ) : (
          <div className="flex w-full flex-col gap-4">
            <div className="flex justify-end">
              <Button variant="outline" onClick={openAddForm}>
                <PlusIcon className="mr-2 h-4 w-4" />
                {t.settings.tools.addServer}
              </Button>
            </div>

            {Object.keys(servers).length === 0 ? (
              <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
                {t.settings.tools.emptyState}
              </div>
            ) : (
              Object.entries(servers).map(([name, serverConfig]) => (
                <Item className="w-full" variant="outline" key={name}>
                  <ItemContent>
                    <ItemTitle>
                      <div className="flex items-center gap-2">
                        <div>{name}</div>
                      </div>
                    </ItemTitle>
                    <ItemDescription className="line-clamp-4">
                      {serverConfig.description}
                    </ItemDescription>
                  </ItemContent>
                  <ItemActions>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="shrink-0"
                      onClick={() => openEditForm(name, serverConfig)}
                      title={t.common.edit}
                      aria-label={t.common.edit}
                    >
                      <PenLineIcon className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-destructive hover:text-destructive shrink-0"
                      onClick={() => setDeleteTarget(name)}
                      title={t.common.delete}
                      aria-label={t.common.delete}
                    >
                      <Trash2Icon className="h-4 w-4" />
                    </Button>
                    <Switch
                      checked={serverConfig.enabled}
                      disabled={env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
                      onCheckedChange={(checked) =>
                        enableServer.mutate(
                          { serverName: name, enabled: checked },
                          {
                            onError: (err) => {
                              toast.error(getMCPErrorMessage(err));
                            },
                          },
                        )
                      }
                    />
                  </ItemActions>
                </Item>
              ))
            )}
          </div>
        )}
      </SettingsSection>

      <Dialog
        open={formOpen}
        onOpenChange={(open) => {
          if (!open) closeForm();
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingServer === null
                ? t.settings.tools.addServer
                : t.settings.tools.editServer}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t.settings.tools.serverName}
              </label>
              <Input
                value={form.name}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, name: e.target.value }))
                }
                disabled={editingServer !== null}
                placeholder="e.g. github"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t.settings.tools.serverType}
              </label>
              <Select
                value={form.type}
                onValueChange={(v) =>
                  setForm((prev) => ({
                    ...prev,
                    type: v as MCPServerFormState["type"],
                  }))
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="stdio">stdio</SelectItem>
                  <SelectItem value="sse">sse</SelectItem>
                  <SelectItem value="http">http</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {form.type === "stdio" && (
              <>
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {t.settings.tools.command}
                  </label>
                  <Input
                    value={form.command}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, command: e.target.value }))
                    }
                    placeholder="e.g. npx"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {t.settings.tools.args}
                  </label>
                  <Textarea
                    value={form.args}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, args: e.target.value }))
                    }
                    placeholder={
                      "One argument per line, e.g.\n-y\n@modelcontextprotocol/server-github"
                    }
                    rows={3}
                  />
                </div>
              </>
            )}

            {form.type !== "stdio" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t.settings.tools.url}
                </label>
                <Input
                  value={form.url}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, url: e.target.value }))
                  }
                  placeholder="e.g. http://localhost:3000/sse"
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t.settings.tools.env}
              </label>
              <KeyValueEditor
                value={form.env}
                onChange={(env) => setForm((prev) => ({ ...prev, env }))}
              />
            </div>

            {form.type !== "stdio" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t.settings.tools.headers}
                </label>
                <KeyValueEditor
                  value={form.headers}
                  onChange={(headers) =>
                    setForm((prev) => ({ ...prev, headers }))
                  }
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <Textarea
                value={form.description}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, description: e.target.value }))
                }
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={closeForm}
              disabled={isFormPending}
            >
              {t.common.cancel}
            </Button>
            <Button onClick={() => void handleSave()} disabled={isFormPending}>
              {isFormPending ? t.common.loading : t.common.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.settings.tools.deleteConfirmTitle}</DialogTitle>
            <DialogDescription>
              {t.settings.tools.deleteConfirmDescription}
            </DialogDescription>
          </DialogHeader>
          {deleteTarget && (
            <div className="bg-muted rounded-md border p-3 text-sm">
              <p className="font-medium">{deleteTarget}</p>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              disabled={deleteServer.isPending}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={() => void handleDelete()}
              disabled={deleteServer.isPending}
            >
              {deleteServer.isPending ? t.common.loading : t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
