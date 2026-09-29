import { useQuery } from "@tanstack/react-query";
import { DownloadIcon, LoaderIcon, PackageIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ArtifactRequestError,
  downloadArtifactArchive,
  getArtifactArchiveManifest,
  MAX_ARTIFACT_ARCHIVE_FILES,
} from "@/core/artifacts/api";
import { urlOfArtifact } from "@/core/artifacts/utils";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";
import { installSkill, SkillRequestError } from "@/core/skills/api";
import { isStaticWebsiteOnly } from "@/core/static-mode";
import {
  getFileExtensionDisplayName,
  getFileIcon,
  getFileName,
} from "@/core/utils/files";
import { cn } from "@/lib/utils";

import { useArtifacts } from "./context";

export function ArtifactFileList({
  archiveDownloadsEnabled = true,
  className,
  files,
  runId,
  threadId,
}: {
  archiveDownloadsEnabled?: boolean;
  className?: string;
  files: string[];
  runId?: string;
  threadId: string;
}) {
  const { t } = useI18n();
  const { user } = useAuth();
  const isAdmin = user?.system_role === "super_admin";
  const { select: selectArtifact, setOpen } = useArtifacts();
  const [downloadingArchive, setDownloadingArchive] = useState(false);
  const [selectedArchiveFiles, setSelectedArchiveFiles] = useState(files);
  const [installingFile, setInstallingFile] = useState<string | null>(null);
  const staticWebsiteOnly = isStaticWebsiteOnly();
  useEffect(() => {
    setSelectedArchiveFiles(files);
  }, [files]);
  const { data: archiveManifest } = useQuery({
    queryKey: ["artifact-archive-manifest", threadId, runId],
    queryFn: () => getArtifactArchiveManifest({ threadId, runId: runId! }),
    enabled:
      archiveDownloadsEnabled && runId !== undefined && !staticWebsiteOnly,
    retry: false,
    staleTime: Infinity,
  });
  const archiveCount = archiveManifest?.fileCount;

  const handleClick = useCallback(
    (filepath: string) => {
      selectArtifact(filepath);
      setOpen(true);
    },
    [selectArtifact, setOpen],
  );

  const handleInstallSkill = useCallback(
    async (e: React.MouseEvent, filepath: string) => {
      e.stopPropagation();
      e.preventDefault();

      if (installingFile) return;

      setInstallingFile(filepath);
      try {
        const result = await installSkill({
          thread_id: threadId,
          path: filepath,
        });
        if (result.success) {
          toast.success(result.message);
        } else {
          toast.error(result.message || "Failed to install skill");
        }
      } catch (error) {
        console.error("Failed to install skill:", error);
        if (error instanceof SkillRequestError && error.isAdminRequired) {
          toast.error(t.settings.skills.installAdminRequired);
        } else {
          toast.error("Failed to install skill");
        }
      } finally {
        setInstallingFile(null);
      }
    },
    [threadId, installingFile, t],
  );

  const handleDownloadArchive = useCallback(async () => {
    if (!runId || downloadingArchive) return;

    setDownloadingArchive(true);
    let objectUrl: string | undefined;
    try {
      const { blob, filename } = await downloadArtifactArchive({
        threadId,
        runId,
        paths: selectedArchiveFiles,
      });
      objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.append(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error("Failed to download artifact archive:", error);
      toast.error(
        error instanceof ArtifactRequestError
          ? error.message
          : t.artifactArchive.downloadFailed,
      );
    } finally {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setDownloadingArchive(false);
    }
  }, [downloadingArchive, runId, selectedArchiveFiles, t, threadId]);

  const canDownloadArchive =
    archiveDownloadsEnabled &&
    archiveCount !== undefined &&
    archiveCount > 1 &&
    !staticWebsiteOnly;
  const exceedsArchiveLimit =
    selectedArchiveFiles.length > MAX_ARTIFACT_ARCHIVE_FILES;

  const toggleArchiveFile = useCallback((filepath: string) => {
    setSelectedArchiveFiles((selected) =>
      selected.includes(filepath)
        ? selected.filter((path) => path !== filepath)
        : [...selected, filepath],
    );
  }, []);

  return (
    <div className={cn("flex w-full flex-col gap-4", className)}>
      {canDownloadArchive && (
        <div className="flex flex-col items-start gap-1">
          <Button
            variant="outline"
            disabled={
              downloadingArchive ||
              selectedArchiveFiles.length === 0 ||
              exceedsArchiveLimit
            }
            onClick={handleDownloadArchive}
          >
            {downloadingArchive ? (
              <LoaderIcon className="size-4 animate-spin" />
            ) : (
              <DownloadIcon className="size-4" />
            )}
            {t.artifactArchive.downloadSelected(selectedArchiveFiles.length)}
          </Button>
          <p className="text-muted-foreground type-compact">
            {exceedsArchiveLimit
              ? t.artifactArchive.selectionLimit(MAX_ARTIFACT_ARCHIVE_FILES)
              : t.artifactArchive.selectionNotice}
          </p>
          <p className="text-muted-foreground type-compact">
            {t.artifactArchive.currentVersionNotice}
          </p>
        </div>
      )}
      <ul className="flex w-full flex-col gap-4">
        {files.map((file) => (
          <Card
            key={file}
            className="relative cursor-pointer p-3"
            onClick={() => handleClick(file)}
          >
            <CardHeader className="grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 pr-2 pl-1">
              <CardTitle className="relative min-w-0 pl-8 leading-tight [overflow-wrap:anywhere] break-words">
                <div className="min-w-0">{getFileName(file)}</div>
                <div className="absolute top-2 -left-0.5">
                  {getFileIcon(file, "size-6")}
                </div>
              </CardTitle>
              <CardDescription className="type-compact min-w-0 pl-8">
                {canDownloadArchive && (
                  <label className="mr-2 inline-flex items-center">
                    <input
                      type="checkbox"
                      aria-label={t.artifactArchive.selectFile(
                        getFileName(file),
                      )}
                      checked={selectedArchiveFiles.includes(file)}
                      onClick={(event) => event.stopPropagation()}
                      onChange={() => toggleArchiveFile(file)}
                    />
                  </label>
                )}
                {getFileExtensionDisplayName(file)} file
              </CardDescription>
              <CardAction className="row-span-1 self-center">
                {file.endsWith(".skill") && isAdmin && (
                  <Button
                    variant="ghost"
                    disabled={installingFile === file}
                    onClick={(e) => handleInstallSkill(e, file)}
                  >
                    {installingFile === file ? (
                      <LoaderIcon className="size-4 animate-spin" />
                    ) : (
                      <PackageIcon className="size-4" />
                    )}
                    {t.common.install}
                  </Button>
                )}
                <Button variant="ghost" asChild>
                  <a
                    href={urlOfArtifact({
                      filepath: file,
                      threadId: threadId,
                      download: true,
                    })}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <DownloadIcon className="size-4" />
                    {t.common.download}
                  </a>
                </Button>
              </CardAction>
            </CardHeader>
          </Card>
        ))}
      </ul>
    </div>
  );
}
