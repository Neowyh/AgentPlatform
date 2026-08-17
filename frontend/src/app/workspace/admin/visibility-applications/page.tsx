"use client";

import { ArrowLeftIcon, CheckIcon, XIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { listUsers } from "@/core/admin/api";
import type { User } from "@/core/admin/types";
import { useAuth } from "@/core/auth/AuthProvider";
import {
  listVisibilityApplications,
  reviewVisibilityApplication,
  withdrawVisibilityApplication,
} from "@/core/visibility-applications/api";
import type { VisibilityApplication } from "@/core/visibility-applications/types";

const STATUS_LABELS: Record<string, string> = {
  pending: "待审批",
  approved: "已批准",
  rejected: "已拒绝",
  withdrawn: "已撤回",
};

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive"> =
  {
    pending: "default",
    approved: "secondary",
    rejected: "destructive",
    withdrawn: "secondary",
  };

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  tool: "工具",
  skill: "Skill",
  workflow: "工作流",
  agent: "智能体",
};

const VISIBILITY_LABELS: Record<string, string> = {
  private: "私有",
  department: "部门",
  public: "公开",
};

export default function VisibilityApplicationsPage() {
  const { user: currentUser } = useAuth();

  const [applications, setApplications] = useState<VisibilityApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState<string>("pending");
  const [filterResourceType, setFilterResourceType] = useState<string>("all");
  const [filterVisibility, setFilterVisibility] = useState<string>("all");
  const [filterApplicant, setFilterApplicant] = useState<string>("all");
  const [users, setUsers] = useState<User[]>([]);
  const [reviewingApplication, setReviewingApplication] =
    useState<VisibilityApplication | null>(null);
  const [reviewComment, setReviewComment] = useState("");
  const [withdrawingId, setWithdrawingId] = useState<string | null>(null);
  const [withdrawConfirm, setWithdrawConfirm] =
    useState<VisibilityApplication | null>(null);

  const fetchApplications = useCallback(async () => {
    try {
      const params: Parameters<typeof listVisibilityApplications>[0] = {
        page,
        page_size: 20,
        status: filterStatus,
      };
      if (filterResourceType !== "all")
        params.resource_type = filterResourceType;
      if (filterVisibility !== "all")
        params.target_visibility = filterVisibility;
      if (filterApplicant !== "all") params.applicant_id = filterApplicant;

      const data = await listVisibilityApplications(params);
      setApplications(data.applications);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [
    filterStatus,
    filterResourceType,
    filterVisibility,
    filterApplicant,
    page,
  ]);

  useEffect(() => {
    if (
      currentUser?.system_role !== "super_admin" &&
      currentUser?.system_role !== "department_admin"
    ) {
      return;
    }

    void listUsers({ limit: 500 })
      .then((data) => setUsers(data.users))
      .catch(() => setUsers([]));
  }, [currentUser]);

  useEffect(() => {
    if (
      currentUser?.system_role !== "super_admin" &&
      currentUser?.system_role !== "department_admin"
    ) {
      return;
    }

    void fetchApplications()
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }, [currentUser, fetchApplications]);

  const handleReview = async (action: "approved" | "rejected") => {
    if (!reviewingApplication) return;

    try {
      await reviewVisibilityApplication(
        reviewingApplication.id,
        action,
        reviewComment,
        reviewingApplication.version,
      );
      setReviewingApplication(null);
      setReviewComment("");
      void fetchApplications();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleWithdraw = async () => {
    if (!withdrawConfirm) return;

    try {
      setWithdrawingId(withdrawConfirm.id);
      await withdrawVisibilityApplication(
        withdrawConfirm.id,
        withdrawConfirm.version,
      );
      setWithdrawConfirm(null);
      void fetchApplications();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setWithdrawingId(null);
    }
  };

  const handleFilterStatusChange = (value: string) => {
    setFilterStatus(value);
    setPage(1);
  };

  const handleFilterResourceTypeChange = (value: string) => {
    setFilterResourceType(value);
    setPage(1);
  };

  const handleFilterVisibilityChange = (value: string) => {
    setFilterVisibility(value);
    setPage(1);
  };

  const handleFilterApplicantChange = (value: string) => {
    setFilterApplicant(value);
    setPage(1);
  };

  const applicantName = (applicantId: string) =>
    users.find((u) => u.id === applicantId)?.username ?? applicantId;

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div
      className="flex size-full flex-col"
      data-testid="visibility-applications-page"
    >
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
            <h1 className="text-xl font-semibold">统一审批中心</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              审批所有资源的可见性变更申请
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
        ) : (
          <div className="flex flex-col gap-4">
            {error && (
              <Alert variant="destructive">
                <AlertTitle className="flex items-center justify-between gap-2 pr-1">
                  操作失败
                  <button
                    type="button"
                    aria-label="关闭错误提示"
                    onClick={() => setError(null)}
                  >
                    <XIcon className="h-4 w-4" />
                  </button>
                </AlertTitle>
                <AlertDescription className="whitespace-pre-line">
                  {error}
                </AlertDescription>
              </Alert>
            )}

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3">
              <Select
                value={filterStatus}
                onValueChange={handleFilterStatusChange}
              >
                <SelectTrigger className="w-36">
                  <SelectValue placeholder="状态" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">待审批</SelectItem>
                  <SelectItem value="approved">已批准</SelectItem>
                  <SelectItem value="rejected">已拒绝</SelectItem>
                  <SelectItem value="withdrawn">已撤回</SelectItem>
                  <SelectItem value="all">全部状态</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filterResourceType}
                onValueChange={handleFilterResourceTypeChange}
              >
                <SelectTrigger className="w-36">
                  <SelectValue placeholder="资源类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部类型</SelectItem>
                  <SelectItem value="tool">工具</SelectItem>
                  <SelectItem value="skill">Skill</SelectItem>
                  <SelectItem value="workflow">工作流</SelectItem>
                  <SelectItem value="agent">智能体</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filterVisibility}
                onValueChange={handleFilterVisibilityChange}
              >
                <SelectTrigger className="w-32">
                  <SelectValue placeholder="目标可见性" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部可见性</SelectItem>
                  <SelectItem value="private">私有</SelectItem>
                  <SelectItem value="department">部门</SelectItem>
                  <SelectItem value="public">公开</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filterApplicant}
                onValueChange={handleFilterApplicantChange}
              >
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="申请人" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部申请人</SelectItem>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.username}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <span className="text-muted-foreground ml-auto text-sm">
                共 {total} 条
              </span>
            </div>

            {/* Applications list */}
            {applications.length === 0 ? (
              <Card>
                <CardContent className="flex h-40 items-center justify-center">
                  <p className="text-muted-foreground text-sm">
                    {filterStatus === "pending"
                      ? "没有待审批的申请"
                      : "没有找到申请记录"}
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="flex flex-col gap-2">
                {applications.map((app) => (
                  <Card key={app.id}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-lg">
                          {app.resource_id}
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">
                            {RESOURCE_TYPE_LABELS[app.resource_type] ??
                              app.resource_type}
                          </Badge>
                          <Badge variant={STATUS_VARIANTS[app.status]}>
                            {STATUS_LABELS[app.status]}
                          </Badge>
                        </div>
                      </div>
                      <CardDescription>
                        申请编号: {app.id} | 申请人:{" "}
                        {applicantName(app.applicant_id)} | 可见性:{" "}
                        {VISIBILITY_LABELS[app.current_visibility]} →{" "}
                        {VISIBILITY_LABELS[app.target_visibility]}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-col gap-2">
                        <p className="text-sm">
                          <span className="font-medium">申请理由:</span>{" "}
                          {app.reason || "无"}
                        </p>
                        {app.submitted_at && (
                          <p className="text-muted-foreground text-xs">
                            提交时间:{" "}
                            {new Date(app.submitted_at).toLocaleString()}
                          </p>
                        )}
                        {app.reviewed_at && (
                          <p className="text-muted-foreground text-xs">
                            审批时间:{" "}
                            {new Date(app.reviewed_at).toLocaleString()}
                          </p>
                        )}
                        {app.review_comment && (
                          <p className="text-sm">
                            <span className="font-medium">审批意见:</span>{" "}
                            {app.review_comment}
                          </p>
                        )}
                        {app.status === "pending" && (
                          <div className="mt-2 flex gap-2">
                            <Button
                              size="sm"
                              onClick={() => setReviewingApplication(app)}
                            >
                              审核
                            </Button>
                            {app.applicant_id === currentUser?.id && (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={withdrawingId === app.id}
                                onClick={() => setWithdrawConfirm(app)}
                              >
                                撤回
                              </Button>
                            )}
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  上一页
                </Button>
                <span className="text-muted-foreground text-sm">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一页
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Review Dialog */}
      <Dialog
        open={!!reviewingApplication}
        onOpenChange={(open) => !open && setReviewingApplication(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>审核可见性变更申请</DialogTitle>
            <DialogDescription>
              申请编号: {reviewingApplication?.id}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="grid gap-2">
              <Label>
                资源类型:{" "}
                {RESOURCE_TYPE_LABELS[
                  reviewingApplication?.resource_type ?? ""
                ] ?? reviewingApplication?.resource_type}
              </Label>
              <Label>资源ID: {reviewingApplication?.resource_id}</Label>
              <Label>
                可见性变更:{" "}
                {VISIBILITY_LABELS[
                  reviewingApplication?.current_visibility ?? ""
                ] ?? reviewingApplication?.current_visibility}{" "}
                →{" "}
                {VISIBILITY_LABELS[
                  reviewingApplication?.target_visibility ?? ""
                ] ?? reviewingApplication?.target_visibility}
              </Label>
              <Label>
                申请人:{" "}
                {reviewingApplication
                  ? applicantName(reviewingApplication.applicant_id)
                  : ""}
              </Label>
              <Label>申请理由: {reviewingApplication?.reason ?? "无"}</Label>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="review-comment">审批意见</Label>
              <Textarea
                id="review-comment"
                value={reviewComment}
                onChange={(e) => setReviewComment(e.target.value)}
                placeholder="请输入审批意见..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setReviewingApplication(null)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => handleReview("rejected")}
            >
              <XIcon className="mr-2 h-4 w-4" />
              驳回
            </Button>
            <Button onClick={() => handleReview("approved")}>
              <CheckIcon className="mr-2 h-4 w-4" />
              通过
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Withdraw Confirm Dialog */}
      <Dialog
        open={!!withdrawConfirm}
        onOpenChange={(open) => !open && setWithdrawConfirm(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认撤回</DialogTitle>
            <DialogDescription>
              确定要撤回此申请吗？撤回后无法恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setWithdrawConfirm(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={withdrawingId !== null}
              onClick={handleWithdraw}
            >
              确认撤回
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
