"use client";

import { useRef, useState } from "react";

import {
  type CodeEvidencePackage,
  type EvidenceMode,
  deleteCodeEvidencePackage,
  uploadCodeEvidencePackage,
} from "@/core/uploads/api";

export function FaultZeroingEvidenceControls({
  threadId,
  mode,
  packageInfo,
  onModeChange,
  onPackageChange,
}: {
  threadId: string;
  mode: EvidenceMode;
  packageInfo: CodeEvidencePackage | null;
  onModeChange: (mode: EvidenceMode) => void;
  onPackageChange: (value: CodeEvidencePackage | null) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      onPackageChange(await uploadCodeEvidencePackage(threadId, file));
      onModeChange("code");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "代码包上传失败");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleDelete() {
    if (!packageInfo) return;
    setError(null);
    try {
      await deleteCodeEvidencePackage(threadId, packageInfo.package_id);
      onPackageChange(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "代码包删除失败");
    }
  }

  return (
    <div
      className="type-body bg-background/40 mb-2 flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2"
      data-testid="fault-zeroing-evidence-controls"
    >
      <span className="font-medium">证据模式</span>
      {(["document", "code", "hybrid"] as const).map((value) => (
        <button
          key={value}
          type="button"
          aria-pressed={mode === value}
          className="data-[active=true]:bg-primary data-[active=true]:text-primary-foreground rounded-md border px-2 py-1"
          data-active={mode === value}
          onClick={() => onModeChange(value)}
        >
          {value === "document"
            ? "文档"
            : value === "code"
              ? "代码"
              : "文档 + 代码"}
        </button>
      ))}
      {(mode === "code" || mode === "hybrid") && (
        <>
          <input
            ref={inputRef}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={(event) => void handleFile(event.target.files?.[0])}
          />
          <button
            type="button"
            className="rounded-md border px-2 py-1"
            disabled={uploading || threadId === "new"}
            onClick={() => inputRef.current?.click()}
          >
            {uploading
              ? "正在校验…"
              : packageInfo
                ? `代码包：${packageInfo.original_filename}`
                : "上传 ZIP 代码包"}
          </button>
          {packageInfo && (
            <span className="text-muted-foreground">
              已接收 {packageInfo.accepted.length} 个文件，排除{" "}
              {packageInfo.excluded.length} 个
            </span>
          )}
          {packageInfo && (
            <button
              type="button"
              className="text-destructive rounded-md border px-2 py-1"
              onClick={() => void handleDelete()}
            >
              删除代码包
            </button>
          )}
          {threadId === "new" && (
            <span className="text-muted-foreground">
              请先创建 Thread 后上传代码包
            </span>
          )}
        </>
      )}
      {error && (
        <span role="alert" className="text-destructive">
          {error}
        </span>
      )}
    </div>
  );
}
