"use client";

import { useState } from "react";

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
import type { Skill } from "@/core/skills/type";

interface SkillApplyDialogProps {
  skill: Skill | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (requestLevel: string, reason: string) => void;
}

export function SkillApplyDialog({
  skill,
  open,
  onOpenChange,
  onSubmit,
}: SkillApplyDialogProps) {
  const [requestLevel, setRequestLevel] = useState<string>("department");
  const [reason, setReason] = useState<string>("");

  const handleSubmit = () => {
    onSubmit(requestLevel, reason);
    onOpenChange(false);
    setReason("");
    setRequestLevel("department");
  };

  if (!skill) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>申请开放 Skill: {skill.name}</DialogTitle>
          <DialogDescription>
            选择开放范围并填写申请理由。部门开放需部门管理员审批，全员开放需超级管理员审批。
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label>当前状态: private (仅自己可见)</Label>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="request-level">申请范围</Label>
            <Select value={requestLevel} onValueChange={setRequestLevel}>
              <SelectTrigger id="request-level">
                <SelectValue placeholder="选择申请范围" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="department">
                  部门 (需部门管理员审批)
                </SelectItem>
                <SelectItem value="public">全员 (需超级管理员审批)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="reason">申请理由</Label>
            <Textarea
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="请说明申请开放的原因..."
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSubmit}>提交申请</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
