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
import { useI18n } from "@/core/i18n/hooks";
import type { Skill } from "@/core/skills/type";

interface SkillApplyDialogProps {
  skill: Skill | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (targetVisibility: string, reason: string) => void;
}

export function SkillApplyDialog({
  skill,
  open,
  onOpenChange,
  onSubmit,
}: SkillApplyDialogProps) {
  const { t } = useI18n();
  const [targetVisibility, setTargetVisibility] =
    useState<string>("department");
  const [reason, setReason] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const mountedRef = useRef(true);
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      onSubmit(targetVisibility, reason);
    } finally {
      setIsSubmitting(false);
      onOpenChange(false);
      setReason("");
      setTargetVisibility("department");
    }
  };

  if (!skill) return null;

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
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t.settings.skills.applyDialogCancel}
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {t.settings.skills.applyDialogSubmit}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
