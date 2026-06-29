import { UploadCloudIcon, DocIcon, ImageFileIcon } from "./components/Icons";
import type { ChangeEvent, DragEvent } from "react";

type UploadCardProps = {
  selectedFile: File | null;
  isDragOver: boolean;
  onDrop: (event: DragEvent<HTMLLabelElement>) => void;
  onDragOver: (event: DragEvent<HTMLLabelElement>) => void;
  onDragLeave: () => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
};

function formatSize(value: number): string {
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export default function UploadCard({
  selectedFile,
  isDragOver,
  onDrop,
  onDragOver,
  onDragLeave,
  onFileChange
}: UploadCardProps) {
  return (
    <label
      className={`upload-card${isDragOver ? " drag-over" : ""}`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={onFileChange} />
      <span className="file-stack" aria-hidden="true">
        <DocIcon size={56} />
        <ImageFileIcon size={38} />
      </span>
      <strong>上传杂志或论文</strong>
      <small>{selectedFile ? `${selectedFile.name} · ${formatSize(selectedFile.size)}` : "支持 PDF、JPG、PNG，单文件不超过 50MB"}</small>
      <span className="ghost-button">
        <UploadCloudIcon size={20} />
        点击上传或拖拽文件到此处
      </span>
    </label>
  );
}
