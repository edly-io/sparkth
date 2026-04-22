"use client";

import { FileText, Download, Pencil, Trash2 } from "lucide-react";
import { RagStatusIndicator } from "./RagStatusIndicator";
import { Button } from "@/components/ui/Button";
import { DriveFile, formatFileSize, formatDate } from "@/lib/drive";
import type { FolderDetailAction } from "./FolderDetail";
import type { RagStatusMap } from "@/lib/useRagStatusPolling";

interface FileTableProps {
  files: DriveFile[];
  editingFileId: number | null;
  editName: string;
  actionFileId: number | null;
  ragStatuses: RagStatusMap;
  dispatch: React.Dispatch<FolderDetailAction>;
  onDownload: (file: DriveFile) => void;
  onRename: (file: DriveFile) => void;
  onDelete: (file: DriveFile) => void;
}

export function FileTable({
  files,
  editingFileId,
  editName,
  actionFileId,
  ragStatuses,
  dispatch,
  onDownload,
  onRename,
  onDelete,
}: FileTableProps) {
  return (
    <table className="w-full table-fixed">
      <colgroup>
        <col className="w-[38%]" />
        <col className="w-[12%]" />
        <col className="w-[15%]" />
        <col className="w-[15%]" />
        <col className="w-[20%]" />
      </colgroup>
      <thead>
        <tr className="border-b border-border">
          <th className="px-6 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Name
          </th>
          <th className="px-6 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Size
          </th>
          <th className="px-6 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Modified
          </th>
          <th className="px-6 py-2.5 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Status
          </th>
          <th className="px-6 py-2.5 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Actions
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {files.map((file) => (
          <tr key={file.id} className="hover:bg-surface-variant/50 transition-colors">
            <td className="px-6 py-3">
              <div className="flex items-center gap-3 min-w-0">
                <FileText className="h-4 w-4 text-secondary-500 shrink-0" />
                {editingFileId === file.id ? (
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => dispatch({ type: "SET_EDIT_NAME", name: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") onRename(file);
                      if (e.key === "Escape") dispatch({ type: "CANCEL_EDIT" });
                    }}
                    className="text-sm text-foreground bg-input border border-border rounded-md px-2 py-1 focus:border-primary-500 focus:outline-none w-full"
                    ref={(el) => el?.focus()}
                  />
                ) : (
                  <span className="text-sm text-foreground truncate" title={file.name}>
                    {file.name}
                  </span>
                )}
              </div>
            </td>
            <td className="px-6 py-3 whitespace-nowrap text-sm text-muted-foreground">
              {formatFileSize(file.size)}
            </td>
            <td className="px-6 py-3 whitespace-nowrap text-sm text-muted-foreground">
              {formatDate(file.modified_time)}
            </td>
            <td className="px-6 py-3 whitespace-nowrap text-center">
              <RagStatusIndicator
                fileId={file.id}
                status={ragStatuses[file.id]?.status ?? null}
                error={ragStatuses[file.id]?.error}
              />
            </td>
            <td className="px-6 py-3 whitespace-nowrap text-right">
              <div className="flex justify-end gap-1">
                {editingFileId === file.id ? (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRename(file)}
                      disabled={actionFileId === file.id}
                    >
                      Save
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => dispatch({ type: "CANCEL_EDIT" })}
                    >
                      Cancel
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => onDownload(file)}
                      disabled={actionFileId === file.id}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() =>
                        dispatch({ type: "START_EDIT", fileId: file.id, name: file.name })
                      }
                      disabled={actionFileId === file.id}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-error-500"
                      onClick={() => onDelete(file)}
                      disabled={actionFileId === file.id}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </>
                )}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
