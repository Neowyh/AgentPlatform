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
import { useI18n } from "@/core/i18n/hooks";
import {
  listVisibilityApplications,
  reviewVisibilityApplication,
  withdrawVisibilityApplication,
} from "@/core/visibility-applications/api";
import type { VisibilityApplication } from "@/core/visibility-applications/types";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive"> =
  {
    pending: "default",
    approved: "secondary",
    rejected: "destructive",
    withdrawn: "secondary",
  };

export default function VisibilityApplicationsPage() {
  const { user: currentUser } = useAuth();
  const { t } = useI18n();

  const statusLabels: Record<string, string> = {
    pending: t.admin.visibilityApplications.statusPending,
    approved: t.admin.visibilityApplications.statusApproved,
    rejected: t.admin.visibilityApplications.statusRejected,
    withdrawn: t.admin.visibilityApplications.statusWithdrawn,
  };

  const resourceTypeLabels: Record<string, string> = {
    tool: t.admin.visibilityApplications.resourceTypeTool,
    skill: t.admin.visibilityApplications.resourceTypeSkill,
    workflow: t.admin.visibilityApplications.resourceTypeWorkflow,
    agent: t.admin.visibilityApplications.resourceTypeAgent,
  };

  const visibilityLabels: Record<string, string> = {
    private: t.admin.visibilityApplications.visibilityPrivate,
    department: t.admin.visibilityApplications.visibilityDepartment,
    public: t.admin.visibilityApplications.visibilityPublic,
  };

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
            <h1 className="type-page-title font-semibold">
              {t.admin.visibilityApplications.pageTitle}
            </h1>
            <p className="text-muted-foreground type-body mt-0.5">
              {t.admin.visibilityApplications.pageDescription}
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-muted-foreground type-body flex h-40 items-center justify-center">
            {t.admin.visibilityApplications.loading}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {error && (
              <Alert variant="destructive">
                <AlertTitle className="flex items-center justify-between gap-2 pr-1">
                  {t.admin.visibilityApplications.operationFailed}
                  <button
                    type="button"
                    aria-label={t.admin.visibilityApplications.closeError}
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
                  <SelectValue
                    placeholder={t.admin.visibilityApplications.status}
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">
                    {t.admin.visibilityApplications.statusPending}
                  </SelectItem>
                  <SelectItem value="approved">
                    {t.admin.visibilityApplications.statusApproved}
                  </SelectItem>
                  <SelectItem value="rejected">
                    {t.admin.visibilityApplications.statusRejected}
                  </SelectItem>
                  <SelectItem value="withdrawn">
                    {t.admin.visibilityApplications.statusWithdrawn}
                  </SelectItem>
                  <SelectItem value="all">
                    {t.admin.visibilityApplications.allStatuses}
                  </SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filterResourceType}
                onValueChange={handleFilterResourceTypeChange}
              >
                <SelectTrigger className="w-36">
                  <SelectValue
                    placeholder={t.admin.visibilityApplications.resourceType}
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    {t.admin.visibilityApplications.allTypes}
                  </SelectItem>
                  <SelectItem value="tool">
                    {t.admin.visibilityApplications.resourceTypeTool}
                  </SelectItem>
                  <SelectItem value="skill">
                    {t.admin.visibilityApplications.resourceTypeSkill}
                  </SelectItem>
                  <SelectItem value="workflow">
                    {t.admin.visibilityApplications.resourceTypeWorkflow}
                  </SelectItem>
                  <SelectItem value="agent">
                    {t.admin.visibilityApplications.resourceTypeAgent}
                  </SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filterVisibility}
                onValueChange={handleFilterVisibilityChange}
              >
                <SelectTrigger className="w-32">
                  <SelectValue
                    placeholder={
                      t.admin.visibilityApplications.targetVisibility
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    {t.admin.visibilityApplications.allVisibilities}
                  </SelectItem>
                  <SelectItem value="private">
                    {t.admin.visibilityApplications.visibilityPrivate}
                  </SelectItem>
                  <SelectItem value="department">
                    {t.admin.visibilityApplications.visibilityDepartment}
                  </SelectItem>
                  <SelectItem value="public">
                    {t.admin.visibilityApplications.visibilityPublic}
                  </SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filterApplicant}
                onValueChange={handleFilterApplicantChange}
              >
                <SelectTrigger className="w-40">
                  <SelectValue
                    placeholder={t.admin.visibilityApplications.applicant}
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    {t.admin.visibilityApplications.allApplicants}
                  </SelectItem>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.username}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <span className="text-muted-foreground type-body ml-auto">
                {t.admin.visibilityApplications.totalCount(total)}
              </span>
            </div>

            {/* Applications list */}
            {applications.length === 0 ? (
              <Card>
                <CardContent className="flex h-40 items-center justify-center">
                  <p className="text-muted-foreground type-body">
                    {filterStatus === "pending"
                      ? t.admin.visibilityApplications.emptyPending
                      : t.admin.visibilityApplications.emptyNotFound}
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="flex flex-col gap-2">
                {applications.map((app) => (
                  <Card key={app.id}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="type-body">
                          {app.resource_id}
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">
                            {resourceTypeLabels[app.resource_type] ??
                              app.resource_type}
                          </Badge>
                          <Badge variant={STATUS_VARIANTS[app.status]}>
                            {statusLabels[app.status]}
                          </Badge>
                        </div>
                      </div>
                      <CardDescription>
                        {t.admin.visibilityApplications.applicationId}: {app.id}{" "}
                        | {t.admin.visibilityApplications.applicant}:{" "}
                        {applicantName(app.applicant_id)} |{" "}
                        {t.admin.visibilityApplications.visibility}:{" "}
                        {visibilityLabels[app.current_visibility]} →{" "}
                        {visibilityLabels[app.target_visibility]}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-col gap-2">
                        <p className="type-body">
                          <span className="font-medium">
                            {t.admin.visibilityApplications.reason}:
                          </span>{" "}
                          {app.reason || t.admin.visibilityApplications.none}
                        </p>
                        {app.submitted_at && (
                          <p className="text-muted-foreground type-body">
                            {t.admin.visibilityApplications.submittedAt}:{" "}
                            {new Date(app.submitted_at).toLocaleString()}
                          </p>
                        )}
                        {app.reviewed_at && (
                          <p className="text-muted-foreground type-body">
                            {t.admin.visibilityApplications.reviewedAt}:{" "}
                            {new Date(app.reviewed_at).toLocaleString()}
                          </p>
                        )}
                        {app.review_comment && (
                          <p className="type-body">
                            <span className="font-medium">
                              {t.admin.visibilityApplications.reviewComment}:
                            </span>{" "}
                            {app.review_comment}
                          </p>
                        )}
                        {app.status === "pending" && (
                          <div className="mt-2 flex gap-2">
                            <Button
                              size="sm"
                              onClick={() => setReviewingApplication(app)}
                            >
                              {t.admin.visibilityApplications.review}
                            </Button>
                            {app.applicant_id === currentUser?.id && (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={withdrawingId === app.id}
                                onClick={() => setWithdrawConfirm(app)}
                              >
                                {t.admin.visibilityApplications.withdraw}
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
                  {t.admin.visibilityApplications.previousPage}
                </Button>
                <span className="text-muted-foreground type-body">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {t.admin.visibilityApplications.nextPage}
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
            <DialogTitle>
              {t.admin.visibilityApplications.reviewDialogTitle}
            </DialogTitle>
            <DialogDescription>
              {t.admin.visibilityApplications.applicationId}:{" "}
              {reviewingApplication?.id}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="grid gap-2">
              <Label>
                {t.admin.visibilityApplications.resourceType}:{" "}
                {resourceTypeLabels[
                  reviewingApplication?.resource_type ?? ""
                ] ?? reviewingApplication?.resource_type}
              </Label>
              <Label>
                {t.admin.visibilityApplications.resourceId}:{" "}
                {reviewingApplication?.resource_id}
              </Label>
              <Label>
                {t.admin.visibilityApplications.visibilityChange}:{" "}
                {visibilityLabels[
                  reviewingApplication?.current_visibility ?? ""
                ] ?? reviewingApplication?.current_visibility}{" "}
                →{" "}
                {visibilityLabels[
                  reviewingApplication?.target_visibility ?? ""
                ] ?? reviewingApplication?.target_visibility}
              </Label>
              <Label>
                {t.admin.visibilityApplications.applicant}:{" "}
                {reviewingApplication
                  ? applicantName(reviewingApplication.applicant_id)
                  : ""}
              </Label>
              <Label>
                {t.admin.visibilityApplications.reason}:{" "}
                {reviewingApplication?.reason ??
                  t.admin.visibilityApplications.none}
              </Label>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="review-comment">
                {t.admin.visibilityApplications.reviewComment}
              </Label>
              <Textarea
                id="review-comment"
                value={reviewComment}
                onChange={(e) => setReviewComment(e.target.value)}
                placeholder={
                  t.admin.visibilityApplications.reviewCommentPlaceholder
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setReviewingApplication(null)}
            >
              {t.admin.visibilityApplications.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={() => handleReview("rejected")}
            >
              <XIcon className="mr-2 h-4 w-4" />
              {t.admin.visibilityApplications.reject}
            </Button>
            <Button onClick={() => handleReview("approved")}>
              <CheckIcon className="mr-2 h-4 w-4" />
              {t.admin.visibilityApplications.approve}
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
            <DialogTitle>
              {t.admin.visibilityApplications.confirmWithdraw}
            </DialogTitle>
            <DialogDescription>
              {t.admin.visibilityApplications.withdrawConfirmDescription}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setWithdrawConfirm(null)}>
              {t.admin.visibilityApplications.cancel}
            </Button>
            <Button
              variant="destructive"
              disabled={withdrawingId !== null}
              onClick={handleWithdraw}
            >
              {t.admin.visibilityApplications.confirmWithdraw}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
