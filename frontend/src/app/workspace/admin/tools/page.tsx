"use client";

import { ArrowLeftIcon, PlayIcon, WrenchIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { listTools, testTool } from "@/core/admin/api";
import { useAuth } from "@/core/auth/AuthProvider";
import type { Tool } from "@/core/tools/types";

export default function ToolsPage() {
  const { user } = useAuth();
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [testInput, setTestInput] = useState("{}");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    // Only fetch data for authorized users
    if (
      user?.system_role !== "super_admin" &&
      user?.system_role !== "department_admin"
    )
      return;

    listTools()
      .then((data) => setTools(data.tools))
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }, [user]);

  const openDetail = (tool: Tool) => {
    setSelectedTool(tool);
    setTestInput(JSON.stringify(tool.param_schema ?? {}, null, 2));
    setTestResult(null);
    setDetailOpen(true);
  };

  const handleTest = async () => {
    if (!selectedTool) return;
    setTesting(true);
    setTestResult(null);
    try {
      let parsedInput: Record<string, unknown>;
      try {
        parsedInput = JSON.parse(testInput) as Record<string, unknown>;
      } catch {
        setTestResult("Error: Invalid JSON input");
        return;
      }
      const data = await testTool(selectedTool.name, parsedInput);
      setTestResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setTestResult(
        `Error: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="flex size-full flex-col">
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <Link href="/workspace/admin">
            <Button variant="ghost" size="icon-sm">
              <ArrowLeftIcon className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-base font-semibold">工具管理</h1>
            <p className="text-muted-foreground mt-0.5 text-base">
              查看和测试系统工具
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-muted-foreground flex h-40 items-center justify-center text-base">
            加载中...
          </div>
        ) : error ? (
          <div className="text-destructive flex h-40 items-center justify-center text-base">
            {error}
          </div>
        ) : tools.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
            <WrenchIcon className="text-muted-foreground h-10 w-10" />
            <p className="text-muted-foreground text-base">暂无工具</p>
          </div>
        ) : (
          <div
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
            data-testid="tool-list"
          >
            {tools.map((tool) => (
              <Card
                key={tool.name}
                className="cursor-pointer transition-shadow hover:shadow-md"
                onClick={() => openDetail(tool)}
                data-testid="tool-card"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <div className="bg-primary/10 flex h-9 w-9 items-center justify-center rounded-lg">
                        <WrenchIcon className="text-primary h-5 w-5" />
                      </div>
                      <div>
                        <CardTitle className="text-base">{tool.name}</CardTitle>
                        <div className="mt-0.5 flex items-center gap-1">
                          {tool.visibility && (
                            <Badge
                              className={
                                tool.visibility === "public"
                                  ? "bg-green-100 text-green-800"
                                  : tool.visibility === "department"
                                    ? "bg-blue-100 text-blue-800"
                                    : "bg-gray-100 text-gray-800"
                              }
                            >
                              {tool.visibility}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                    <Badge
                      variant={tool.requires_network ? "secondary" : "default"}
                    >
                      {tool.requires_network ? "需联网" : "可用"}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription className="line-clamp-2 text-base">
                    {tool.description || "暂无描述"}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Detail & Test Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedTool?.name}</DialogTitle>
            <DialogDescription>{selectedTool?.description}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge
                variant={
                  selectedTool?.requires_network ? "secondary" : "default"
                }
              >
                {selectedTool?.requires_network ? "需联网" : "可用"}
              </Badge>
              {selectedTool?.visibility && (
                <Badge
                  className={
                    selectedTool.visibility === "public"
                      ? "bg-green-100 text-green-800"
                      : selectedTool.visibility === "department"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-gray-100 text-gray-800"
                  }
                >
                  {selectedTool.visibility}
                </Badge>
              )}
            </div>
            <div className="space-y-2">
              <label className="text-base font-medium">测试输入 (JSON)</label>
              <Textarea
                className="font-mono text-base"
                rows={6}
                value={testInput}
                onChange={(e) => setTestInput(e.target.value)}
                placeholder='{"key": "value"}'
              />
            </div>
            <Button onClick={handleTest} disabled={testing}>
              <PlayIcon className="mr-1.5 h-4 w-4" />
              {testing ? "测试中..." : "测试工具"}
            </Button>
            {testResult !== null && (
              <div className="space-y-2">
                <label className="text-base font-medium">测试结果</label>
                <pre className="bg-muted max-h-64 overflow-auto rounded-md p-4 text-base">
                  {testResult}
                </pre>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailOpen(false)}>
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
