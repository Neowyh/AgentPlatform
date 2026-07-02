"use client";

import { ArrowLeftIcon, CheckIcon, XIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

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
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/core/auth/AuthProvider";
import {
  listSkillApplications,
  reviewSkillApplication,
} from "@/core/skills/api";

interface SkillApplication {
  id: string;
  skill_id: string;
  skill_name: string;
  applicant_id: string;
  request_level: string;
  department_id: string | null;
  reason: string;
  status: string;
  submitted_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comment: string | null;
}

const STATUS_LABELS: Record<string, string> = {
  pending: "待审批",
  approved: "已批准",
  rejected: "已拒绝",
};

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive"> =
  {
    pending: "default",
    approved: "secondary",
    rejected: "destructive",
  };

const REQUEST_LEVEL_LABELS: Record<string, string> = {
  department: "部门",
  public: "全员",
};

export default function SkillApplicationsPage() {
  const { user: currentUser } = useAuth();
  const router = useRouter();
  const [applications, setApplications] = useState<SkillApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>("pending");
  const [reviewingApplication, setReviewingApplication] =
    useState<SkillApplication | null>(null);
  const [reviewComment, setReviewComment] = useState<string>("");

  const fetchApplications = useCallback(async () => {
    try {
      const data = await listSkillApplications(
        filterStatus === "all" ? undefined : filterStatus,
      );
      setApplications(data.applications);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [filterStatus]);

  useEffect(() => {
    // Only fetch data for authorized users
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

  // Role check: only super_admin and department_admin can access this page
  if (
    currentUser?.system_role !== "super_admin" &&
    currentUser?.system_role !== "department_admin"
  ) {
    router.replace("/workspace");
    return null;
  }

  const handleReview = async (action: "approved" | "rejected") => {
    if (!reviewingApplication) return;

    try {
      await reviewSkillApplication(
        reviewingApplication.id,
        action,
        reviewComment,
      );
      setReviewingApplication(null);
      setReviewComment("");
      void fetchApplications();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const filteredApplications = applications.filter(
    (app) => filterStatus === "all" || app.status === filterStatus,
  );

  return (
    <div
      className="flex size-full flex-col"
      data-testid="skill-applications-page"
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
            <h1 className="text-xl font-semibold">Skill 开放申请审批</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              审批用户提交的 Skill 开放申请
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
            {/* Status filter */}
            <div className="flex gap-2">
              <Button
                variant={filterStatus === "pending" ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterStatus("pending")}
              >
                待审批 (
                {applications.filter((a) => a.status === "pending").length})
              </Button>
              <Button
                variant={filterStatus === "approved" ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterStatus("approved")}
              >
                已批准 (
                {applications.filter((a) => a.status === "approved").length})
              </Button>
              <Button
                variant={filterStatus === "rejected" ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterStatus("rejected")}
              >
                已拒绝 (
                {applications.filter((a) => a.status === "rejected").length})
              </Button>
              <Button
                variant={filterStatus === "all" ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterStatus("all")}
              >
                全部
              </Button>
            </div>

            {/* Applications list */}
            {filteredApplications.length === 0 ? (
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
                {filteredApplications.map((app) => (
                  <Card key={app.id}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-lg">
                          {app.skill_name}
                        </CardTitle>
                        <Badge variant={STATUS_VARIANTS[app.status]}>
                          {STATUS_LABELS[app.status]}
                        </Badge>
                      </div>
                      <CardDescription>
                        申请编号: {app.id} | 申请人: {app.applicant_id} |
                        申请范围: {REQUEST_LEVEL_LABELS[app.request_level]}
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
                        {app.status === "pending" && (
                          <div className="mt-2 flex gap-2">
                            <Button
                              size="sm"
                              onClick={() => setReviewingApplication(app)}
                            >
                              审核
                            </Button>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
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
            <DialogTitle>审核 Skill 开放申请</DialogTitle>
            <DialogDescription>
              申请编号: {reviewingApplication?.id}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="grid gap-2">
              <Label>申请 Skill: {reviewingApplication?.skill_name}</Label>
              <Label>申请人: {reviewingApplication?.applicant_id}</Label>
              <Label>
                申请范围:{" "}
                {REQUEST_LEVEL_LABELS[
                  reviewingApplication?.request_level ?? ""
                ] ?? reviewingApplication?.request_level}
              </Label>
              <Label>申请理由: {reviewingApplication?.reason ?? "无"}</Label>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="comment">审批意见</Label>
              <Textarea
                id="comment"
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
              拒绝
            </Button>
            <Button onClick={() => handleReview("approved")}>
              <CheckIcon className="mr-2 h-4 w-4" />
              批准
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
