import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function sv(props: IconProps, defaultSize: number) {
  const s = props.size ?? defaultSize;
  return {
    width: s,
    height: s,
    viewBox: props.viewBox ?? `0 0 ${defaultSize} ${defaultSize}`,
  };
}

export function DocIcon(props: IconProps) {
  return (
    <svg {...sv(props, 32)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Document file">
      <path d="M20.5 3.5H9A3 3 0 0 0 6 6.5v19A3 3 0 0 0 9 28.5h14a3 3 0 0 0 3-3V9l-5.5-5.5Z" fill="currentColor" opacity=".14" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M20.5 3.8V8a1 1 0 0 0 1 1h4.2M10.5 15h11M10.5 19h11M10.5 23h7" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function ImageFileIcon(props: IconProps) {
  return (
    <svg {...sv(props, 32)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Image file">
      <rect x="5" y="5" width="22" height="22" rx="4" fill="currentColor" opacity=".1"/>
      <rect x="5" y="5" width="22" height="22" rx="4" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="12" cy="12" r="2.1" fill="currentColor" opacity=".55"/>
      <path d="M8.5 22.4 14 16.8a1.3 1.3 0 0 1 1.82-.03l2.05 1.95 2.55-2.95a1.35 1.35 0 0 1 2.05.03l2.95 3.55" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function UploadCloudIcon(props: IconProps) {
  return (
    <svg {...sv(props, 24)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Upload">
      <path d="M7.6 17.8H7a4 4 0 0 1-.55-7.96A5.7 5.7 0 0 1 17.25 8.2a4.8 4.8 0 0 1-.1 9.6h-.75" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12 18V10.6m0 0-3.05 3.05M12 10.6l3.05 3.05" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function LogoBookIcon(props: IconProps) {
  return (
    <svg {...sv(props, 28)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Mag2Read logo">
      <path d="M6.25 5.6C6.25 4.72 6.97 4 7.85 4h6.05c1.25 0 2.4.5 3.25 1.3.85-.8 2-1.3 3.25-1.3h.75c.88 0 1.6.72 1.6 1.6v16.35c0 .52-.5.9-1 .76l-1.9-.52a7.6 7.6 0 0 0-5.9.77c-.5.3-1.12.3-1.62 0a7.6 7.6 0 0 0-5.9-.77l-1.18.32A.78.78 0 0 1 4.25 21.76V7.1" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M14 5.3v17M8.75 8.3h3.25M8.75 11.4h3.25M19.25 8.3h2.1M19.25 11.4h2.1" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/>
      <path d="M5.25 14.5h4.5M5.25 17h6.1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".55"/>
    </svg>
  );
}

export function CheckCircleIcon(props: IconProps) {
  return (
    <svg {...sv(props, 22)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Success">
      <circle cx="11" cy="11" r="8.5" fill="currentColor" opacity=".14"/>
      <circle cx="11" cy="11" r="8.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="m7.4 11.1 2.25 2.25 5-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <svg {...sv(props, 18)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Expand">
      <path d="m4.5 7 4.5 4 4.5-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function DownloadIcon(props: IconProps) {
  return (
    <svg {...sv(props, 20)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Download">
      <path d="M10 3.5v8.2m0 0 3.2-3.2M10 11.7 6.8 8.5" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M4 14.2v.85A2.45 2.45 0 0 0 6.45 17.5h7.1A2.45 2.45 0 0 0 16 15.05v-.85" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round"/>
    </svg>
  );
}

export function AiSparkleIcon(props: IconProps) {
  return (
    <svg {...sv(props, 22)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="AI">
      <path d="M9.1 2.7c.5 3 2.25 4.75 5.25 5.25-3 .5-4.75 2.25-5.25 5.25-.5-3-2.25-4.75-5.25-5.25 3-.5 4.75-2.25 5.25-5.25Z" fill="currentColor"/>
      <path d="M16.5 10.9c.32 1.92 1.43 3.03 3.35 3.35-1.92.32-3.03 1.43-3.35 3.35-.32-1.92-1.43-3.03-3.35-3.35 1.92-.32 3.03-1.43 3.35-3.35Z" fill="currentColor" opacity=".72"/>
    </svg>
  );
}

export function ProgressClockIcon(props: IconProps) {
  return (
    <svg {...sv(props, 22)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Processing">
      <circle cx="11" cy="11" r="8.3" fill="currentColor" opacity=".12"/>
      <circle cx="11" cy="11" r="8.3" stroke="currentColor" strokeWidth="1.35"/>
      <path d="M11 6.6V11l3 1.8" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function PdfIcon(props: IconProps) {
  return (
    <svg {...sv(props, 32)} fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="PDF file">
      <rect x="6" y="3.5" width="18" height="25" rx="3.2" fill="currentColor" opacity=".12"/>
      <path d="M20.5 3.5H9.2A3.2 3.2 0 0 0 6 6.7v18.6a3.2 3.2 0 0 0 3.2 3.2h13.6a3.2 3.2 0 0 0 3.2-3.2V9l-5.5-5.5Z" stroke="currentColor" strokeWidth="1.45" strokeLinejoin="round"/>
      <path d="M20.5 3.8V8a1 1 0 0 0 1 1h4.2" stroke="currentColor" strokeWidth="1.45" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M10.5 20.9c2.15-1.1 4.35-3.75 5.25-7.3.35-1.42-.15-2.55-.9-2.43-.88.14-.9 1.8-.38 3.15.9 2.32 2.8 4.88 5.28 5.65 1.23.38 2.2.1 2.13-.58-.1-1.1-3.52-.78-6.42-.1-2.15.5-4.95 1.15-4.96 1.61Z" stroke="currentColor" strokeWidth="1.18" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

/** 根据文件名后缀返回合适的文件图标 */
export function FileTypeIcon({ name, size }: { name: string; size?: number }) {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  const s = size ?? 18;
  if (ext === "pdf") return <PdfIcon size={s} />;
  if (["jpg", "jpeg", "png", "gif", "bmp", "webp"].includes(ext)) return <ImageFileIcon size={s} />;
  return <DocIcon size={s} />;
}
