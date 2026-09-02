"use client";

import { type Dispatch, type SetStateAction, useRef, useState } from "react";

import {
  type CodeEvidencePackage,
  deleteCodeEvidencePackage,
  uploadCodeEvidencePackage,
} from "@/core/uploads/api";

export function FaultZeroingEvidenceControls({
  threadId,
  packageInfo,
  onPackageChange,
  pendingFile,
  onPendingFileChange,
}: {
  threadId: string;
  packageInfo: CodeEvidencePackage | null;
  onPackageChange: Dispatch<SetStateAction<CodeEvidencePackage | null>>;
  pendingFile: File | null;
  onPendingFileChange: (file: File | null) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      if (threadId === "new") {
        onPendingFileChange(file);
      } else {
        onPackageChange(await uploadCodeEvidencePackage(threadId, file));
      }
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
    const packageId = packageInfo.package_id;
    setDeleting(true);
    try {
      await deleteCodeEvidencePackage(threadId, packageId);
      onPackageChange((current) =>
        current?.package_id === packageId ? null : current,
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "代码包删除失败");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div
      className="type-body bg-background/40 mb-2 flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2"
      data-testid="fault-zeroing-evidence-controls"
    >
      <span className="font-medium">可选代码材料</span>
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
          disabled={uploading || deleting}
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
            disabled={uploading || deleting}
            onClick={() => void handleDelete()}
          >
            删除代码包
          </button>
        )}
        {threadId === "new" && !pendingFile && (
          <span className="text-muted-foreground">
            可先选择，发送时自动上传
          </span>
        )}
      </>

      {pendingFile && !packageInfo && (
        <span className="text-muted-foreground">
          待发送时上传：{pendingFile.name}
        </span>
      )}
      {error && (
        <span role="alert" className="text-destructive">
          {error}
        </span>
      )}
    </div>
  );
}
