"use client";

import { ArrowLeftIcon, PlusIcon, TrashIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/core/auth/AuthProvider";

interface SkillDefaultConfig {
  id: string;
  scope: string;
  scope_id: string | null;
  skill_name: string;
  enabled: boolean;
  user_override_allowed: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export default function SkillDefaultsPage() {
  const { user: currentUser } = useAuth();
  const router = useRouter();
  const [configs, setConfigs] = useState<SkillDefaultConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("global");
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newSkillName, setNewSkillName] = useState<string>("");
  const [newEnabled, setNewEnabled] = useState<boolean>(true);
  const [newUserOverrideAllowed, setNewUserOverrideAllowed] =
    useState<boolean>(true);

  const fetchConfigs = useCallback(async () => {
    try {
      // TODO: Replace with actual API call
      // const data = await listSkillDefaults({ scope: activeTab });
      // setConfigs(data.configs);
      setConfigs([]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    // Only fetch data for authorized users
    if (
      currentUser?.system_role !== "super_admin" &&
      currentUser?.system_role !== "department_admin"
    ) {
      return;
    }

    void fetchConfigs()
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }, [currentUser, fetchConfigs]);

  // Role check: only super_admin and department_admin can access this page
  if (
    currentUser?.system_role !== "super_admin" &&
    currentUser?.system_role !== "department_admin"
  ) {
    router.replace("/workspace");
    return null;
  }

  const handleAddConfig = async () => {
    try {
      // TODO: Replace with actual API call
      // await createSkillDefault({
      //   scope: activeTab,
      //   scope_id: activeTab === "department" ? currentUser?.department_id : undefined,
      //   skill_name: newSkillName,
      //   enabled: newEnabled,
      //   user_override_allowed: newUserOverrideAllowed,
      // });
      console.log("Adding config:", {
        scope: activeTab,
        skill_name: newSkillName,
        enabled: newEnabled,
        user_override_allowed: newUserOverrideAllowed,
      });
      setShowAddDialog(false);
      setNewSkillName("");
      setNewEnabled(true);
      setNewUserOverrideAllowed(true);
      void fetchConfigs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleDeleteConfig = async (configId: string) => {
    try {
      // TODO: Replace with actual API call
      // await deleteSkillDefault(configId);
      console.log("Deleting config:", configId);
      void fetchConfigs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleToggleEnabled = async (
    config: SkillDefaultConfig,
    enabled: boolean,
  ) => {
    try {
      // TODO: Replace with actual API call
      // await updateSkillDefault(config.id, { enabled });
      console.log("Updating config:", { id: config.id, enabled });
      void fetchConfigs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleToggleUserOverride = async (
    config: SkillDefaultConfig,
    userOverrideAllowed: boolean,
  ) => {
    try {
      // TODO: Replace with actual API call
      // await updateSkillDefault(config.id, { user_override_allowed: userOverrideAllowed });
      console.log("Updating config:", {
        id: config.id,
        user_override_allowed: userOverrideAllowed,
      });
      void fetchConfigs();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const filteredConfigs = configs.filter(
    (config) => activeTab === "all" || config.scope === activeTab,
  );

  return (
    <div className="flex size-full flex-col" data-testid="skill-defaults-page">
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-4">
          <Link
            href="/workspace/admin"
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeftIcon className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-xl font-semibold">Skill 默认配置</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              管理全局和部门级别的 Skill 默认启用配置
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-muted-foreground flex h-40 items-center justify-center text-sm">
            加载中...
          </div>
        ) : error ? (
          <div className="text-destructive flex h-40 items-center justify-center text-sm">
            {error}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Scope tabs */}
            <div className="flex items-center justify-between">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList>
                  {currentUser?.system_role === "super_admin" && (
                    <TabsTrigger value="global">全局</TabsTrigger>
                  )}
                  <TabsTrigger value="department">部门</TabsTrigger>
                </TabsList>
              </Tabs>
              <Button size="sm" onClick={() => setShowAddDialog(true)}>
                <PlusIcon className="mr-2 h-4 w-4" />
                添加默认配置
              </Button>
            </div>

            {/* Configs list */}
            {filteredConfigs.length === 0 ? (
              <Card>
                <CardContent className="flex h-40 items-center justify-center">
                  <p className="text-muted-foreground text-sm">
                    没有找到默认配置
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="flex flex-col gap-2">
                {filteredConfigs.map((config) => (
                  <Card key={config.id}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-lg">
                          {config.skill_name}
                        </CardTitle>
                        <Badge variant="outline">{config.scope}</Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="flex items-center gap-2">
                            <Label className="text-sm">启用:</Label>
                            <Switch
                              checked={config.enabled}
                              onCheckedChange={(checked) =>
                                handleToggleEnabled(config, checked)
                              }
                            />
                          </div>
                          <div className="flex items-center gap-2">
                            <Label className="text-sm">允许用户覆盖:</Label>
                            <Switch
                              checked={config.user_override_allowed}
                              onCheckedChange={(checked) =>
                                handleToggleUserOverride(config, checked)
                              }
                            />
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => handleDeleteConfig(config.id)}
                        >
                          <TrashIcon className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Description */}
            <Card className="mt-4">
              <CardContent className="pt-6">
                <div className="text-muted-foreground space-y-2 text-sm">
                  <p>• 全局配置对所有部门生效</p>
                  <p>• 部门配置仅对本部门生效，优先级高于全局配置</p>
                  <p>
                    • 允许用户覆盖: 用户可以在个人偏好中修改此 skill 的启用状态
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Add Config Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加默认配置</DialogTitle>
            <DialogDescription>
              为 {activeTab === "global" ? "全局" : "部门"} 添加 Skill 默认配置
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="grid gap-2">
              <Label htmlFor="skill-name">Skill 名称</Label>
              <Input
                id="skill-name"
                value={newSkillName}
                onChange={(e) => setNewSkillName(e.target.value)}
                placeholder="例如: deep-research"
              />
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Label className="text-sm">启用:</Label>
                <Switch checked={newEnabled} onCheckedChange={setNewEnabled} />
              </div>
              <div className="flex items-center gap-2">
                <Label className="text-sm">允许用户覆盖:</Label>
                <Switch
                  checked={newUserOverrideAllowed}
                  onCheckedChange={setNewUserOverrideAllowed}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              取消
            </Button>
            <Button onClick={handleAddConfig}>添加</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
