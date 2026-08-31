"use client";

import { useState, useRef, useEffect } from "react";

import { Button } from "@/components/ui/button";
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
import { VisibilityImpactPanel } from "@/components/workspace/resources/visibility-impact-panel";
import { useI18n } from "@/core/i18n/hooks";
import type { Skill } from "@/core/skills/type";
import { classifyVisibilityChange } from "@/core/visibility-applications/options";

interface SkillApplyDialogProps {
  skill: Skill | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (targetVisibility: string, reason: string) => void | Promise<void>;
  onChange: (
    targetVisibility: string,
    cascade: boolean,
  ) => void | Promise<void>;
}

export function SkillApplyDialog({
  skill,
  open,
  onOpenChange,
  onSubmit,
  onChange,
}: SkillApplyDialogProps) {
  const { t } = useI18n();
  const [targetVisibility, setTargetVisibility] =
    useState<string>("department");
  const [reason, setReason] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [confirmingDowngrade, setConfirmingDowngrade] =
    useState<boolean>(false);
  const [cascadeDowngrade, setCascadeDowngrade] = useState<boolean>(false);
  const mountedRef = useRef(true);
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (skill) {
      setTargetVisibility(skill.visibility ?? "private");
      setReason("");
      setConfirmingDowngrade(false);
      setCascadeDowngrade(false);
    }
  }, [skill]);

  if (!skill) return null;

  const change = classifyVisibilityChange(skill.visibility, targetVisibility);

  const resetForm = () => {
    setReason("");
    setTargetVisibility(skill.visibility ?? "private");
    setConfirmingDowngrade(false);
    setCascadeDowngrade(false);
  };

  const handleSubmit = async () => {
    if (change === "unchanged") return;
    if (change === "downgrade") {
      setConfirmingDowngrade(true);
      return;
    }
    setIsSubmitting(true);
    try {
      await onSubmit(targetVisibility, reason);
    } finally {
      if (mountedRef.current) {
        setIsSubmitting(false);
        onOpenChange(false);
        resetForm();
      }
    }
  };

  const handleConfirmDowngrade = async () => {
    setIsSubmitting(true);
    try {
      await onChange(targetVisibility, cascadeDowngrade);
    } finally {
      if (mountedRef.current) {
        setIsSubmitting(false);
        onOpenChange(false);
        resetForm();
      }
    }
  };

  if (confirmingDowngrade) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>
              {t.settings.skills.applyDialogDowngradeConfirmTitle}
            </DialogTitle>
            <DialogDescription>
              {t.settings.skills.applyDialogDowngradeConfirmDescription}
            </DialogDescription>
          </DialogHeader>
          <VisibilityImpactPanel
            resourceId={skill.resource_id ?? skill.name}
            currentVisibility={skill.visibility ?? "private"}
            targetVisibility={targetVisibility}
            onCascadeChange={setCascadeDowngrade}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmingDowngrade(false)}
            >
              {t.settings.skills.applyDialogCancel}
            </Button>
            <Button onClick={handleConfirmDowngrade} disabled={isSubmitting}>
              {t.settings.skills.applyDialogConfirm}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {t.settings.skills.applyDialogTitle.replace("{name}", skill.name)}
          </DialogTitle>
          <DialogDescription>
            {t.settings.skills.applyDialogDescription}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label>
              {t.settings.skills.applyDialogCurrentVisibility.replace(
                "{visibility}",
                skill.visibility ?? "private",
              )}
            </Label>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="target-visibility">
              {t.settings.skills.applyDialogTargetVisibility}
            </Label>
            <Select
              value={targetVisibility}
              onValueChange={setTargetVisibility}
            >
              <SelectTrigger id="target-visibility">
                <SelectValue
                  placeholder={t.settings.skills.applyDialogTargetVisibility}
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="private">
                  {t.settings.skills.applyDialogVisibilityPrivate}
                </SelectItem>
                <SelectItem value="department">
                  {t.settings.skills.applyDialogVisibilityDepartment}
                </SelectItem>
                <SelectItem value="public">
                  {t.settings.skills.applyDialogVisibilityPublic}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          {change === "upgrade" && (
            <p className="text-muted-foreground type-body">
              {t.settings.skills.applyDialogUpgradeHint}
            </p>
          )}
          {change === "downgrade" && (
            <p className="text-muted-foreground type-body">
              {t.settings.skills.applyDialogDowngradeHint}
            </p>
          )}
          {change !== "downgrade" && (
            <div className="grid gap-2">
              <Label htmlFor="reason">
                {t.settings.skills.applyDialogReason}
              </Label>
              <Textarea
                id="reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={t.settings.skills.applyDialogReasonPlaceholder}
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t.settings.skills.applyDialogCancel}
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting || change === "unchanged"}
          >
            {t.settings.skills.applyDialogSubmit}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
