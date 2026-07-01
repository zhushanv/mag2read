import {
  ArrowLeft,
  FileCode2,
  FileText,
  MessageSquareText,
  Pencil,
  RefreshCw,
  RotateCcw,
  Save,
  X
} from "lucide-react";
import {
  LogoBookIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  DownloadIcon,
  AiSparkleIcon,
  ProgressClockIcon,
  FileTypeIcon,
} from "./components/Icons";
 import { createElement, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import PipelineFlow from "./components/PipelineFlow";
// FluidBackground removed — using CSS-only background
import type { CSSProperties, ChangeEvent, DragEvent, FormEvent } from "react";
import UploadCard from "./UploadCard";
import heroImage from "../icons/heroPage/hero-transparent.png";
import structureImage from "../icons/heroPage/structure-transparent.png";
import ocrImage from "../icons/heroPage/ocr-transparent.png";
import exportImage from "../icons/heroPage/exportFile-transparent.png";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const STAGE_ORDER = ["render", "layout_detect", "layout_refine", "ocr", "text_cleaning", "document_build", "export"];
const STAGE_LABELS: Record<string, string> = {
  render: "页面渲染",
  layout_detect: "版面分析",
  layout_refine: "规则清洗",
  ocr: "文字识别",
  text_cleaning: "文本整理",
  document_build: "结构构建",
  export: "文件导出",
  ai_reading: "AI 导读"
};

type Task = {
  id: number;
  task_id: string;
  original_name: string;
  input_type: string;
  status: string;
  current_stage: string | null;
  progress: number;
  page_count: number | null;
  output_format: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

type TaskStep = {
  id: number;
  task_id: string;
  stage: string;
  status: string;
  progress: number;
  duration_ms: number | null;
  summary_json: Record<string, unknown> | null;
  error_message: string | null;
};

type ExportRecord = {
  id: number;
  task_id: string;
  format: string;
  file_path: string | null;
  file_size: number | null;
  status: string;
  error_message: string | null;
  created_at: string;
};

type TaskFile = {
  id: number;
  file_role: string;
  file_name: string;
  file_size: number | null;
  page_no: number | null;
};

type TaskPage = {
  id: number;
  task_id: string;
  page_no: number;
  image_path: string;
  width: number | null;
  height: number | null;
  quality_status: string | null;
  page_type: string | null;
  layout_type: string | null;
  ocr_status: string | null;
  avg_confidence: string | number | null;
  need_review: boolean;
};

type TaskBundle = {
  task: Task;
  steps: TaskStep[];
  exports: ExportRecord[];
  files: TaskFile[];
};

type TaskSocketMessage =
  | {
      type: "task_update";
      task: Task;
      steps: TaskStep[];
    }
  | {
      type: "task_missing";
      task_id: string;
    };
type ProcessingMode = "auto" | "local" | "cloud";

type AuthUser = {
  id: number;
  email: string | null;
  display_name: string | null;
  avatar_url: string | null;
  role: string;
};

type BBox = {
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
};

type ExplainBlock = {
  block_id?: string;
  id?: string | number;
  role?: string;
  type?: string;
  text?: string;
  bbox?: BBox;
  is_noise?: boolean;
  noise_reason?: string | null;
  order?: number | null;
  line_count?: number;
  ocr_confidence?: number | null;
  confidence?: Record<string, number | string | null> | null;
  layout_confidence?: Record<string, number | string | null> | null;
};

type ExplainPageData = {
  page_no?: number;
  width?: number;
  height?: number;
  page_type?: string;
  layout_type?: string;
  blocks?: ExplainBlock[];
};

type CleanBlock = {
  id?: string;
  block_id?: string;
  type?: string;
  role?: string;
  level?: number;
  text?: string;
  page_no?: number;
  is_graphical?: boolean;
  bbox?: BBox;
  media_path?: string | null;
  media_width?: number | null;
  media_height?: number | null;
  source_pages?: number[];
  source_block_ids?: string[];
  ocr_confidence?: number | null;
  _block_index?: number;
};

type CleanPage = {
  page_no?: number;
  blocks?: CleanBlock[];
};

type CleanDocument = {
  title?: string;
  pages?: CleanPage[];
  blocks?: CleanBlock[];
  stats?: Record<string, unknown>;
};

type EditableDocumentResponse = {
  task_id: string;
  source: "clean" | "edited";
  has_edited: boolean;
  document_path: string;
  base_document_path: string;
  document: CleanDocument;
  manual_edit?: Record<string, unknown> | null;
};

type ParagraphLevelValue = "paragraph" | "heading1" | "heading2" | "heading3" | "note" | "caption";

type ParagraphLevelOption = {
  value: ParagraphLevelValue;
  label: string;
  type: string;
  role: string;
  level?: number;
};

const PARAGRAPH_LEVEL_OPTIONS: ParagraphLevelOption[] = [
  { value: "paragraph", label: "正文", type: "paragraph", role: "body" },
  { value: "heading1", label: "一级标题", type: "heading", role: "heading", level: 1 },
  { value: "heading2", label: "二级标题", type: "heading", role: "heading", level: 2 },
  { value: "heading3", label: "三级标题", type: "heading", role: "heading", level: 3 },
  { value: "note", label: "引用/注释", type: "note", role: "note" },
  { value: "caption", label: "图片说明", type: "caption", role: "caption" },
];

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const text = await response.text();
    let message: string | null = null;
    try {
      const payload = JSON.parse(text) as { detail?: unknown; message?: unknown };
      const detail = payload.detail ?? payload.message;
      if (typeof detail === "string") {
        message = detail;
      }
    } catch {
      message = null;
    }
    throw new Error(message || text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function websocketUrl(path: string): string {
  const base = API_BASE || window.location.origin;
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function formatTime(value: string | null): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function formatSize(value: number | null): string {
  if (!value) return "-";
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function safeNumber(value: unknown, fallback = 0): number {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : fallback;
}

function blockKey(block: ExplainBlock, index: number): string {
  return String(block.block_id ?? block.id ?? `${block.role ?? block.type ?? "block"}-${index}`);
}

function blockRole(block: ExplainBlock): string {
  return String(block.role ?? block.type ?? "unknown");
}

function roleLabel(role: string): string {
  const labels: Record<string, string> = {
    title: "标题",
    heading: "标题",
    body: "正文",
    paragraph: "正文",
    text: "正文",
    caption: "图注",
    figure: "图片",
    image: "图片",
    table: "表格",
    header: "页眉",
    footer: "页脚",
    page_number: "页码",
    formula: "公式",
    unknown: "未知"
  };
  return labels[role] ?? role;
}

function roleClassName(block: ExplainBlock): string {
  if (block.is_noise) return "noise";
  const role = blockRole(block);
  if (["title", "heading"].includes(role)) return "title";
  if (["caption", "figure", "image"].includes(role)) return "caption";
  if (role === "table") return "table";
  if (["header", "footer", "page_number"].includes(role)) return "noise";
  if (role === "unknown") return "unknown";
  return "body";
}

function blockConfidence(block: ExplainBlock): string {
  const raw =
    block.ocr_confidence ??
    block.confidence?.detector ??
    block.confidence?.score ??
    block.layout_confidence?.detector ??
    block.layout_confidence?.score;
  if (raw === null || raw === undefined || raw === "") return "-";
  const value = safeNumber(raw);
  if (value <= 1) return `${Math.round(value * 100)}%`;
  return `${Math.round(value)}%`;
}

function mergeExplainBlocks(layout: ExplainPageData | null, ocr: ExplainPageData | null): ExplainBlock[] {
  const layoutBlocks = layout?.blocks ?? [];
  const ocrBlocks = ocr?.blocks ?? [];
  const ocrById = new Map<string, ExplainBlock>();
  ocrBlocks.forEach((block, index) => ocrById.set(blockKey(block, index), block));

  if (layoutBlocks.length > 0) {
    return layoutBlocks.map((layoutBlock, index) => {
      const key = blockKey(layoutBlock, index);
      const ocrBlock = ocrById.get(key);
      return {
        ...layoutBlock,
        ...ocrBlock,
        bbox: ocrBlock?.bbox ?? layoutBlock.bbox,
        role: ocrBlock?.role ?? layoutBlock.role,
        is_noise: layoutBlock.is_noise,
        noise_reason: layoutBlock.noise_reason
      };
    });
  }

  return ocrBlocks;
}

function cleanBlocksFromDocument(document: CleanDocument | null): CleanBlock[] {
  if (!document) return [];
  if (Array.isArray(document.blocks)) {
    return document.blocks.map((block, index) => ({ ...block, _block_index: index }));
  }
  return (document.pages ?? []).flatMap((page) =>
    (page.blocks ?? []).map((block, index) => ({
      ...block,
      page_no: block.page_no ?? page.page_no,
      _block_index: index,
    }))
  );
}

function cleanBlockHasMedia(block: CleanBlock): boolean {
  return Boolean(block.is_graphical || ["figure", "image", "table", "formula"].includes(String(block.role ?? block.type ?? "")));
}

function cleanBlockMediaUrl(taskId: string, block: CleanBlock): string | null {
  if (!block.media_path) return null;
  const filename = block.media_path.split("/").filter(Boolean).pop();
  if (!filename) return null;
  return `${API_BASE}/api/tasks/${taskId}/media/${encodeURIComponent(filename)}`;
}

function paragraphLevelForBlock(block: CleanBlock): ParagraphLevelValue {
  const type = String(block.type ?? "").toLowerCase();
  const role = String(block.role ?? "").toLowerCase();
  if (type === "heading" || role === "title" || role === "heading") {
    const level = Number(block.level ?? (role === "title" ? 1 : 2));
    if (level <= 1) return "heading1";
    if (level === 2) return "heading2";
    return "heading3";
  }
  if (type === "caption" || role === "caption") return "caption";
  if (type === "note" || role === "note" || type === "sidebar" || role === "sidebar") return "note";
  return "paragraph";
}

function paragraphOption(value: ParagraphLevelValue): ParagraphLevelOption {
  return PARAGRAPH_LEVEL_OPTIONS.find((option) => option.value === value) ?? PARAGRAPH_LEVEL_OPTIONS[0];
}

function editBlockClassName(block: CleanBlock): string {
  const level = paragraphLevelForBlock(block);
  if (level.startsWith("heading")) return level;
  if (level === "note") return "note";
  if (level === "caption") return "caption";
  if (block.type === "formula" || block.role === "formula") return "formula";
  return "";
}

function readingBlockClassName(block: CleanBlock): string {
  const level = paragraphLevelForBlock(block);
  if (level.startsWith("heading")) return "clean-heading";
  if (level === "note") return "clean-note";
  if (level === "caption") return "media-caption";
  if (block.type === "formula" || block.role === "formula") return "clean-formula";
  return "";
}

function readingBlockTag(block: CleanBlock): "p" | "h1" | "h2" | "h3" {
  const level = paragraphLevelForBlock(block);
  if (level === "heading1") return "h1";
  if (level === "heading2") return "h2";
  if (level === "heading3") return "h3";
  return "p";
}

function cleanBlockKey(block: CleanBlock, index: number): string {
  const sourceKey = Array.isArray(block.source_block_ids) ? block.source_block_ids.join("|") : "";
  return String(block.id || block.block_id || sourceKey || `${block.page_no ?? "p"}-${block._block_index ?? index}`);
}

function cloneCleanDocument(document: CleanDocument): CleanDocument {
  return JSON.parse(JSON.stringify(document)) as CleanDocument;
}

function updateCleanDocumentBlockText(document: CleanDocument, targetKey: string, text: string): CleanDocument {
  const next = cloneCleanDocument(document);
  if (Array.isArray(next.blocks)) {
    next.blocks = next.blocks.map((block, index) => (cleanBlockKey(block, index) === targetKey ? { ...block, text } : block));
    return next;
  }
  next.pages = (next.pages ?? []).map((page) => ({
    ...page,
    blocks: (page.blocks ?? []).map((block, index) => (cleanBlockKey({ ...block, page_no: block.page_no ?? page.page_no }, index) === targetKey ? { ...block, text } : block))
  }));
  return next;
}

function applyParagraphLevel(block: CleanBlock, value: ParagraphLevelValue): CleanBlock {
  const option = paragraphOption(value);
  const next: CleanBlock = {
    ...block,
    type: option.type,
    role: option.role,
  };
  if (option.level) {
    next.level = option.level;
  } else {
    delete next.level;
  }
  return next;
}

function updateCleanDocumentBlockLevel(document: CleanDocument, targetKey: string, value: ParagraphLevelValue): CleanDocument {
  const next = cloneCleanDocument(document);
  if (Array.isArray(next.blocks)) {
    next.blocks = next.blocks.map((block, index) => (cleanBlockKey(block, index) === targetKey ? applyParagraphLevel(block, value) : block));
    return next;
  }
  next.pages = (next.pages ?? []).map((page) => ({
    ...page,
    blocks: (page.blocks ?? []).map((block, index) => (
      cleanBlockKey({ ...block, page_no: block.page_no ?? page.page_no }, index) === targetKey ? applyParagraphLevel(block, value) : block
    ))
  }));
  return next;
}

function fitTextareaToContent(element: HTMLTextAreaElement | null) {
  if (!element) return;
  requestAnimationFrame(() => {
    element.style.height = "auto";
    element.style.height = `${element.scrollHeight}px`;
  });
}

function AutoSizeTextarea({ value, className, placeholder, onChange }: {
  value: string;
  className?: string;
  placeholder?: string;
  onChange: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      className={className}
      value={value}
      rows={1}
      placeholder={placeholder}
      onChange={onChange}
    />
  );
}

function stageStatus(stage: string, task: Task, step?: TaskStep): "done" | "active" | "failed" | "wait" {
  if (step?.status === "failed") return "failed";
  if (step?.status === "success" || step?.status === "skipped") return "done";
  if (task.current_stage === stage || step?.status === "processing") return "active";
  return "wait";
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [bundle, setBundle] = useState<TaskBundle | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [showLanding, setShowLanding] = useState(true);
  const [showLogin, setShowLogin] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [formats, setFormats] = useState<string[]>(["epub", "docx", "markdown", "html"]);
  const processingMode: ProcessingMode = "auto";
 const autoStart = true;
 const [aiOpen, setAiOpen] = useState(false);
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState<string | null>(null);
 const [dragOver, setDragOver] = useState(false);
 const [showFinish, setShowFinish] = useState(false);
 const finalizedTaskRef = useRef<string | null>(null);

  const currentTask = bundle?.task ?? tasks.find((item) => item.task_id === selectedTaskId) ?? null;

  async function loadCurrentUser() {
    try {
      const user = await requestJson<AuthUser>("/api/auth/me");
      setCurrentUser(user);
    } catch {
      setCurrentUser(null);
    } finally {
      setAuthReady(true);
    }
  }

  async function loadTasks() {
    if (!currentUser) {
      setTasks([]);
      return;
    }
    const result = await requestJson<Task[]>("/api/tasks?limit=20");
    setTasks(result);
  }

  useEffect(() => {
    setShowFinish(false);
  }, [selectedTaskId]);

  async function loadTaskBundle(taskId: string) {
    const [task, steps, exports, files] = await Promise.all([
      requestJson<Task>(`/api/tasks/${taskId}`),
      requestJson<TaskStep[]>(`/api/tasks/${taskId}/steps`),
      requestJson<ExportRecord[]>(`/api/tasks/${taskId}/exports`),
      requestJson<TaskFile[]>(`/api/tasks/${taskId}/files`)
    ]);
    setBundle({ task, steps, exports, files });
  }

  useEffect(() => {
    loadCurrentUser();
  }, []);

  useEffect(() => {
    if (!authReady) return;
    loadTasks().catch((reason: unknown) => setError(String(reason)));
  }, [authReady, currentUser]);

  useEffect(() => {
    if (!selectedTaskId) return;
    loadTaskBundle(selectedTaskId).catch((reason: unknown) => setError(String(reason)));
  }, [selectedTaskId]);

  useEffect(() => {
    if (!selectedTaskId) return;

    let closedByEffect = false;
    const socket = new WebSocket(websocketUrl(`/ws/tasks/${selectedTaskId}`));

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as TaskSocketMessage;
      if (message.type === "task_missing") {
        setError("任务不存在或已被删除");
        return;
      }

      setBundle((value) => {
        if (!value || value.task.task_id !== message.task.task_id) return value;
        return {
          ...value,
          task: message.task,
          steps: message.steps
        };
      });
      setTasks((value) => value.map((item) => (item.task_id === message.task.task_id ? message.task : item)));

      if (["success", "failed", "cancelled"].includes(message.task.status) && finalizedTaskRef.current !== message.task.task_id) {
        finalizedTaskRef.current = message.task.task_id;
        loadTaskBundle(message.task.task_id).catch(() => undefined);
        loadTasks().catch(() => undefined);
      }
    };

    socket.onerror = () => {
      if (!closedByEffect) {
        loadTaskBundle(selectedTaskId).catch(() => undefined);
      }
    };

    return () => {
      closedByEffect = true;
      socket.close();
    };
  }, [selectedTaskId]);

  const stepMap = useMemo(() => {
    const map = new Map<string, TaskStep>();
    bundle?.steps.forEach((step) => map.set(step.stage, step));
    return map;
  }, [bundle]);

  function pickFile(file: File | null) {
    setSelectedFile(file);
    setError(null);
  }

 function onDrop(event: DragEvent<HTMLLabelElement>) {
   event.preventDefault();
   setDragOver(false);
   pickFile(event.dataTransfer.files.item(0));
 }

 function onFileChange(event: ChangeEvent<HTMLInputElement>) {
   pickFile(event.target.files?.item(0) ?? null);
 }

 function onDragOver(event: DragEvent) {
   event.preventDefault();
   setDragOver(true);
 }
 
 function onDragLeave() {
   setDragOver(false);
 }
 
  async function uploadFile(event: FormEvent) {
    event.preventDefault();
    if (!currentUser) {
      setShowLogin(true);
      setShowLanding(false);
      return;
    }
    if (!selectedFile) {
      setError("请选择 PDF、JPG 或 PNG 文件");
      return;
    }
    if (formats.length === 0) {
      setError("至少选择一种导出格式");
      return;
    }

    setLoading(true);
    setError(null);
    const data = new FormData();
    data.append("file", selectedFile);
    data.append("output_format", formats.join(","));
    data.append("processing_mode", processingMode);
    data.append("auto_start", String(autoStart));

    try {
      const task = await requestJson<Task>("/api/tasks/upload", {
        method: "POST",
        body: data
      });
      setSelectedTaskId(task.task_id);
      setSelectedFile(null);
      await loadTasks();
      await loadTaskBundle(task.task_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }

 const toggleFormat = useCallback((format: string) => {
    setFormats((prev) =>
      prev.includes(format) ? prev.filter((f) => f !== format) : [...prev, format]
    );
  }, []);

 return (
   <main className="desktop-shell">

     <TopBar
       isLanding={!currentTask && showLanding}
       currentUser={currentUser}
       onRefresh={() => loadTasks()}
       onHome={() => {
         setSelectedTaskId(null);
         setBundle(null);
         setShowLanding(true);
         setShowLogin(false);
       }}
       onStart={() => {
         if (currentUser) {
           setShowLanding(false);
           setShowLogin(false);
         } else {
           setShowLanding(false);
           setShowLogin(true);
         }
       }}
       onLogin={() => {
         setShowLanding(false);
         setShowLogin(true);
       }}
       onLogout={async () => {
         await requestJson("/api/auth/logout", { method: "POST" }).catch(() => undefined);
         setCurrentUser(null);
         setTasks([]);
         setSelectedTaskId(null);
         setBundle(null);
         setShowLanding(true);
         setShowLogin(false);
       }}
     />

      {error && (
        <div className="notice">
          <span>{error}</span>
          <button aria-label="关闭提示" onClick={() => setError(null)}>
            <X size={16} />
          </button>
        </div>
      )}
     <AnimatePresence mode="wait">
     {!currentTask && showLogin && (
       <motion.div
         key="login"
         initial={{ opacity: 0, y: 20 }}
         animate={{ opacity: 1, y: 0 }}
         exit={{ opacity: 0, y: -16 }}
         transition={{ duration: 0.3, ease: "easeInOut" }}
       >
        <LoginPanel
          onBack={() => {
            setShowLogin(false);
            setShowLanding(true);
          }}
          onSuccess={(user) => {
            setCurrentUser(user);
            setShowLogin(false);
            setShowLanding(false);
            loadTasks().catch(() => undefined);
          }}
        />
       </motion.div>
     )}

     {!currentTask && !showLogin && showLanding && (
       <motion.div
         key="landing"
         initial={{ opacity: 0, y: 20 }}
         animate={{ opacity: 1, y: 0 }}
         exit={{ opacity: 0, y: -16 }}
         transition={{ duration: 0.3, ease: "easeInOut" }}
       >
        <LandingPage onStart={() => {
          if (currentUser) {
            setShowLanding(false);
          } else {
            setShowLanding(false);
            setShowLogin(true);
          }
        }} />
       </motion.div>
     )}

     {!currentTask && !showLogin && !showLanding && (
       <motion.div
         key="upload"
         initial={{ opacity: 0, y: 20 }}
         animate={{ opacity: 1, y: 0 }}
         exit={{ opacity: 0, y: -16 }}
         transition={{ duration: 0.3, ease: "easeInOut" }}
       >
       <HomePanel
         selectedFile={selectedFile}
         dragOver={dragOver}
         loading={loading}
         tasks={tasks}
         formats={formats}
         onToggleFormat={toggleFormat}
         onDrop={onDrop}
         onDragOver={onDragOver}
         onDragLeave={onDragLeave}
         onFileChange={onFileChange}
         onSubmit={uploadFile}
         onSelectTask={setSelectedTaskId}
       />
       </motion.div>
     )}

     {currentTask && bundle && !showFinish && (
       <motion.div
         key="working"
         initial={{ opacity: 0, y: 20 }}
         animate={{ opacity: 1, y: 0 }}
         exit={{ opacity: 0, y: -16 }}
         transition={{ duration: 0.3, ease: "easeInOut" }}
       >
       <WorkingPanel
         bundle={bundle}
         stepMap={stepMap}
         aiOpen={aiOpen}
         onBack={() => {
           setSelectedTaskId(null);
           setBundle(null);
         }}
         onOpenAi={() => setAiOpen(true)}
         onCloseAi={() => setAiOpen(false)}
         taskCompleted={currentTask.status === "success"}
         onViewResults={() => setShowFinish(true)}
       />
       </motion.div>
     )}

     {currentTask && bundle && showFinish && (
       <motion.div
         key="finish"
         initial={{ opacity: 0, y: 20 }}
         animate={{ opacity: 1, y: 0 }}
         exit={{ opacity: 0, y: -16 }}
         transition={{ duration: 0.3, ease: "easeInOut" }}
       >
       <FinishPanel
         bundle={bundle}
         onBack={() => {
           setSelectedTaskId(null);
           setBundle(null);
         }}
         onRetry={() => loadTaskBundle(currentTask.task_id)}
       />
      </motion.div>
      )}
     </AnimatePresence>
   </main>
  );
}

function TopBar({
  isLanding,
  currentUser,
  onRefresh,
  onHome,
  onStart,
  onLogin,
  onLogout
}: {
  isLanding: boolean;
  currentUser: AuthUser | null;
  onRefresh: () => void;
  onHome: () => void;
  onStart: () => void;
  onLogin: () => void;
  onLogout: () => void;
}) {
  return (
    <header className="topbar">
      <button className="brand brand-button" type="button" aria-label="返回首页" onClick={onHome}>
        <LogoBookIcon size={22} />
        <strong>Mag2Read</strong>
      </button>
      <div className="top-actions">
        {isLanding ? (
          currentUser ? (
            <>
              <span className="user-chip">{currentUser.display_name || currentUser.email}</span>
              <button className="nav-button secondary" type="button" onClick={onLogout}>退出</button>
            </>
          ) : (
            <>
              <button className="nav-button secondary" type="button" onClick={onLogin}>登录</button>
              <button className="nav-button primary" type="button" onClick={onStart}>免费开始</button>
            </>
          )
        ) : (
          <>
            {currentUser && <span className="user-chip">{currentUser.display_name || currentUser.email}</span>}
            <button className="icon-button" aria-label="刷新任务" onClick={onRefresh}>
              <RefreshCw size={17} />
            </button>
            {currentUser && <button className="nav-button secondary compact" type="button" onClick={onLogout}>退出</button>}
          </>
        )}
      </div>
    </header>
  );
}

function LoginPanel({ onBack, onSuccess }: { onBack: () => void; onSuccess: (user: AuthUser) => void }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [debugCode, setDebugCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function requestCode(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const result = await requestJson<{ message: string; cooldown_seconds: number; debug_code?: string | null }>("/api/auth/email/request-code", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setCodeSent(true);
      setDebugCode(result.debug_code ?? null);
      setMessage(result.debug_code ? `开发环境验证码：${result.debug_code}` : result.message);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }

  async function verifyCode(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const result = await requestJson<{ user: AuthUser }>("/api/auth/email/verify-code", {
        method: "POST",
        body: JSON.stringify({ email, code }),
      });
      onSuccess(result.user);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="login-screen">
      <div className="login-panel">
        <button className="login-back" type="button" onClick={onBack}>
          <ArrowLeft size={18} />
          返回首页
        </button>
        <div className="login-brand">
          <LogoBookIcon size={30} />
          <strong>Mag2Read</strong>
        </div>
        <h1>登录 Mag2Read</h1>
        <p>使用邮箱验证码继续，无需设置密码。</p>

        <form className="login-form" onSubmit={codeSent ? verifyCode : requestCode}>
          <label>
            邮箱
            <input
              type="email"
              value={email}
              placeholder="name@example.com"
              onChange={(event) => setEmail(event.target.value)}
              disabled={loading || codeSent}
              required
            />
          </label>
          {codeSent && (
            <label>
              验证码
              <input
                inputMode="numeric"
                value={code}
                placeholder="请输入 6 位验证码"
                onChange={(event) => setCode(event.target.value)}
                disabled={loading}
                required
              />
            </label>
          )}
          <button className="login-submit" type="submit" disabled={loading}>
            {loading ? "处理中..." : codeSent ? "登录" : "继续"}
          </button>
        </form>

        {message && <p className={debugCode ? "login-debug" : "login-message"}>{message}</p>}
        {codeSent && (
          <button className="login-link" type="button" onClick={() => { setCodeSent(false); setCode(""); setDebugCode(null); }}>
            重新填写邮箱
          </button>
        )}

        <div className="login-divider"><span>OR</span></div>
        <button className="oauth-button" type="button" onClick={() => { window.location.href = `${API_BASE}/api/auth/oauth/google/start`; }}>
          Continue with Google
        </button>
        <button className="oauth-button" type="button" onClick={() => { window.location.href = `${API_BASE}/api/auth/oauth/wechat/start`; }}>
          微信登录
        </button>
        <small>登录即表示你同意 Mag2Read 用于保存转换历史和保护任务访问权限。</small>
      </div>
      <div className="login-preview" aria-hidden="true">
        <img src={heroImage} alt="" />
      </div>
    </section>
  );
}

function LandingPage({ onStart }: { onStart: () => void }) {
  const features = [
    {
      image: structureImage,
      label: "01 · 智能版面分析",
      title: "理解版面，而不只是看见文字",
      description: "自动识别标题、双栏正文、图片、图注与表格，理清阅读顺序，完整保留原文的版面逻辑与结构层级。"
    },
    {
      image: ocrImage,
      label: "02 · 高精度 OCR",
      title: "逐行扫描，精准转录",
      description: "柔和扫描线逐行识别，将扫描件与图片中的文字转换为整齐、可编辑的数字文本，细节清晰，支持多语言。"
    },
    {
      image: exportImage,
      label: "03 · 多文件格式导出",
      title: "一份文档，随处可用",
      description: "整理完成的文档可一键分发为多种格式 —— EPUB、DOCX、Markdown、HTML，随处可读、随时可改。"
    }
  ];

  return (
    <section className="landing-screen">
      <div className="landing-hero">
        <div className="landing-copy">
          <h1>
            把纸质杂志与论文，
            <span>一键变成</span>
            数字文档
          </h1>
          <p className="landing-subtitle">
            Mag2Read 智能识别版面结构，精准还原标题、正文、图片与表格，直接导出 EPUB、DOCX、Markdown、HTML —— 随处可读，随时可改。
          </p>
          <button className="landing-cta" type="button" onClick={onStart}>
            马上开始
          </button>
        </div>
        <div className="landing-visual" aria-hidden="true">
          <img src={heroImage} alt="" />
        </div>
      </div>

      <div className="landing-feature-head">
        <h2>为什么选择 Mag2Read</h2>
        <p>三步连贯的处理流程，温和而有序地还原你文档里的每一处结构。</p>
      </div>

      <div className="landing-feature-grid">
        {features.map((feature) => (
          <article className="landing-feature-card" key={feature.label}>
            <div className="landing-feature-art">
              <img src={feature.image} alt="" />
            </div>
            <p>{feature.label}</p>
            <h3>{feature.title}</h3>
            <span>{feature.description}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

function HomePanel(props: {
  selectedFile: File | null;
  dragOver: boolean;
  loading: boolean;
  tasks: Task[];
  formats: string[];
  onToggleFormat: (format: string) => void;
  onDrop: (event: DragEvent<HTMLLabelElement>) => void;
  onDragOver: (event: DragEvent) => void;
  onDragLeave: () => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (event: FormEvent) => void;
  onSelectTask: (taskId: string) => void;
}) {
  return (
    <section className="home-screen">
      <form className="upload-form" onSubmit={props.onSubmit}>
        <UploadCard
          selectedFile={props.selectedFile}
          isDragOver={props.dragOver}
          onDrop={props.onDrop}
          onDragOver={props.onDragOver}
          onDragLeave={props.onDragLeave}
          onFileChange={props.onFileChange}
        />

        <div className="format-selector">
          <span className="format-selector-label">导出格式</span>
          {[
            { key: 'epub', label: 'EPUB', svg: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M4 3.5h6.5l3.5 3.5v7.5a1.5 1.5 0 0 1-1.5 1.5h-8.5a1.5 1.5 0 0 1-1.5-1.5V5a1.5 1.5 0 0 1 1.5-1.5Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/><path d="M10.5 3.8v3.2h3.2M5.5 9.5h5M5.5 12h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg> },
            { key: 'docx', label: 'DOCX', svg: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><rect x="2.5" y="2.5" width="13" height="13" rx="2.5" stroke="currentColor" strokeWidth="1.2" opacity=".6"/><path d="M5.5 6.5h7M5.5 9h5.5M5.5 11.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".6"/></svg> },
            { key: 'markdown', label: 'Markdown', svg: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M4.5 14V4l4 2.5L12.5 4v10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" opacity=".6"/></svg> },
            { key: 'html', label: 'HTML', svg: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M4 5l2.5 4L4 13" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" opacity=".7"/><path d="M9.5 13L14 9l-4.5-4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" opacity=".7"/></svg> },
          ].map((fmt) => (
            <button
              key={fmt.key}
              className={'format-option' + (props.formats.includes(fmt.key) ? ' active' : '')}
              type="button"
              onClick={() => props.onToggleFormat(fmt.key)}
            >
              {fmt.svg}
              {fmt.label}
            </button>
          ))}
        </div>

        <button className="primary-button" disabled={props.loading} type="submit">
          {props.loading ? "正在创建任务" : "开始解析"}
        </button>
      </form>

      <RecentTasks tasks={props.tasks} onSelectTask={props.onSelectTask} />
    </section>
  );
}

function RecentTasks({ tasks, onSelectTask }: { tasks: Task[]; onSelectTask: (taskId: string) => void }) {
  return (
    <section className="recent">
      <h2>最近转换记录</h2>
      <div className="recent-list">
        {tasks.length === 0 && <p className="empty">暂无任务</p>}
        {tasks.map((task) => (
          <button className="recent-row" key={task.task_id} onClick={() => onSelectTask(task.task_id)}>
            <FileTypeIcon name={task.original_name} size={18} />
            <span className="task-name">{task.original_name}</span>
            <span>{task.page_count ? `${task.page_count} 页` : "-"}</span>
            <span>{formatTime(task.created_at)}</span>
            <StatusBadge status={task.status} />
            <DownloadIcon size={16} />
          </button>
        ))}
      </div>
    </section>
  );
}

function WorkingPanel(props: {
  bundle: TaskBundle;
  stepMap: Map<string, TaskStep>;
  aiOpen: boolean;
  onBack: () => void;
  onOpenAi: () => void;
  onCloseAi: () => void;
  taskCompleted: boolean;
  onViewResults: () => void;
}) {
  const { task } = props.bundle;

  if (!props.taskCompleted) {
    return (
      <section className="task-screen">
        <ProcessingWait
          task={task}
          onBack={props.onBack}
          onViewResults={props.onViewResults}
        />
      </section>
    );
  }

  return (
    <section className="task-screen">
      <TaskHeader task={task} onBack={props.onBack} onViewResults={props.onViewResults} />


      <div className="work-grid">
        <PreviewPane bundle={props.bundle} />
        <TextPane bundle={props.bundle} onOpenAi={props.onOpenAi} />
      </div>

      {props.aiOpen && <AiPanel bundle={props.bundle} onClose={props.onCloseAi} />}
    </section>
  );
}

function ProcessingWait({ task, onBack, onViewResults }: { task: Task; onBack: () => void; onViewResults: () => void }) {
  const [showDot, setShowDot] = useState(true);
  const [dots, setDots] = useState("");

  useEffect(() => {
    const dotTimer = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 600);
    const blinkTimer = setInterval(() => {
      setShowDot((prev) => !prev);
    }, 1200);
    return () => {
      clearInterval(dotTimer);
      clearInterval(blinkTimer);
    };
  }, []);

  return (
    <div className="processing-screen">
      <button className="back-button processing-back" onClick={onBack} aria-label="返回首页">
        <ArrowLeft size={20} />
      </button>

      <div className="processing-center">
        <div className="processing-ring">
          <svg viewBox="0 0 100 100" className="processing-ring-svg">
            <defs>
              <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#1877ff" />
                <stop offset="50%" stopColor="#44dccb" />
                <stop offset="100%" stopColor="#1877ff" />
              </linearGradient>
            </defs>
            <circle
              className="processing-ring-bg"
              cx="50" cy="50" r="40"
              fill="none"
              stroke="#e8ecf0"
              strokeWidth="4"
            />
            <circle
              className="processing-ring-arc"
              cx="50" cy="50" r="40"
              fill="none"
              stroke="url(#ringGrad)"
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray="251"
              strokeDashoffset="80"
            />
          </svg>
          <div className="processing-ring-icon">
            <LogoBookIcon size={28} />
          </div>
        </div>

        <h2 className="processing-title">正在解析文档</h2>
        <p className="processing-desc">
          我们正在智能识别文档中的文字和版面结构
          <span className="processing-dots">{dots}</span>
          <span className={`processing-caret ${showDot ? "" : "hidden"}`}>_</span>
        </p>

        <div className="processing-filename">{task.original_name}</div>
      </div>
    </div>
  );
}

function CompactProgress({ task, stepMap }: { task: Task; stepMap: Map<string, TaskStep> }) {
  const currentLabel = task.current_stage ? STAGE_LABELS[task.current_stage] ?? task.current_stage : "等待调度";

  return (
    <section className="compact-progress" aria-label="转换进度">
      <div className="compact-progress-copy">
        <span>{task.progress < 100 ? "正在转换" : "转换完成"}</span>
        <strong>{currentLabel}</strong>
      </div>
      <div className="compact-progress-track" aria-hidden="true">
        <i style={{ width: `${task.progress}%` }} />
      </div>
      <PipelineFlow stages={STAGE_ORDER} stepMap={stepMap} currentStage={task.current_stage} />
    </section>
  );
}

function TaskHeader({ task, onBack, onViewResults }: { task: Task; onBack: () => void; onViewResults: () => void }) {
  return (
    <div className="task-header">
      <button className="back-button" onClick={onBack} aria-label="返回首页">
        <ArrowLeft size={20} />
      </button>
      <div>
        <h1>任务详情</h1>
        
      </div>
      <div className="task-header-actions">
        <div className="task-header-done">
          <span className="task-header-check">
            <CheckCircleIcon size={14} />
          </span>
          <span>识别完成</span>
        </div>
        <button className="task-header-view" onClick={onViewResults}>
          查看结果
          <ChevronDownIcon size={16} />
        </button>
      </div>
    </div>
  );
}

function PreviewPane({ bundle }: { bundle: TaskBundle }) {
  const pageCount = bundle.task.page_count ?? 1;
  const inputFile = bundle.files.find((file) => file.file_role.startsWith("input"));
  const [pages, setPages] = useState<TaskPage[]>([]);
  const [selectedPageNo, setSelectedPageNo] = useState<number | null>(null);
  const [layoutData, setLayoutData] = useState<ExplainPageData | null>(null);
  const [ocrData, setOcrData] = useState<ExplainPageData | null>(null);
  const [selectedBlockKey, setSelectedBlockKey] = useState<string | null>(null);
  const [previewStatus, setPreviewStatus] = useState<"idle" | "loading" | "ready" | "waiting">("idle");

  useEffect(() => {
    setPreviewStatus("loading");
    requestJson<TaskPage[]>(`/api/tasks/${bundle.task.task_id}/pages`)
      .then((result) => {
        setPages(result);
        setSelectedPageNo((value) => value ?? result[0]?.page_no ?? null);
        setPreviewStatus(result.length > 0 ? "ready" : "waiting");
      })
      .catch(() => {
        setPages([]);
        setSelectedPageNo(null);
        setPreviewStatus("waiting");
      });
  }, [bundle.task.task_id]);

  useEffect(() => {
    if (!selectedPageNo) {
      setLayoutData(null);
      setOcrData(null);
      return;
    }

    setSelectedBlockKey(null);
    Promise.allSettled([
      requestJson<ExplainPageData>(`/api/tasks/${bundle.task.task_id}/pages/${selectedPageNo}/layout`),
      requestJson<ExplainPageData>(`/api/tasks/${bundle.task.task_id}/pages/${selectedPageNo}/ocr`)
    ]).then(([layoutResult, ocrResult]) => {
      setLayoutData(layoutResult.status === "fulfilled" ? layoutResult.value : null);
      setOcrData(ocrResult.status === "fulfilled" ? ocrResult.value : null);
    });
  }, [bundle.task.task_id, bundle.task.status, selectedPageNo]);

  const selectedPage = pages.find((page) => page.page_no === selectedPageNo) ?? null;
  const blocks = mergeExplainBlocks(layoutData, ocrData);
  const selectedBlock =
    blocks.find((block, index) => blockKey(block, index) === selectedBlockKey) ?? blocks.find((block) => Boolean(block.text)) ?? null;
  const pageWidth = safeNumber(layoutData?.width ?? ocrData?.width ?? selectedPage?.width, 1);
  const pageHeight = safeNumber(layoutData?.height ?? ocrData?.height ?? selectedPage?.height, 1);

  return (
    <section className="pane preview-pane">
      <div className="pane-title">
        <h2>原文预览</h2>
        <span>共 {pageCount} 页</span>
      </div>
      {inputFile && (
        <div className="file-summary">
          <span className="file-chip">
            <FileText size={17} />
            {inputFile.file_name}
          </span>
          <span>{formatSize(inputFile.file_size)}</span>
        </div>
      )}

      <div className="explain-stage">
        <div className="page-rail" aria-label="页面列表">
          {pages.length === 0 && <span className="rail-empty">{previewStatus === "loading" ? "读取中" : "等待渲染"}</span>}
          {pages.slice(0, 24).map((page) => (
            <button
              className={page.page_no === selectedPageNo ? "selected" : ""}
              key={page.id}
              type="button"
              onClick={() => setSelectedPageNo(page.page_no)}
            >
              <strong>{page.page_no}</strong>
              <small>{page.need_review ? "复核" : page.quality_status ?? "ok"}</small>
            </button>
          ))}
        </div>

        <div className="preview-col">
          <div className="page-canvas-scroll">
            <div className="page-canvas">
              {selectedPageNo ? (
                <div className="page-canvas-img-wrap">
                  <img alt={`第 ${selectedPageNo} 页预览`} src={`${API_BASE}/api/tasks/${bundle.task.task_id}/pages/${selectedPageNo}/image`} />
                  <div className="block-layer">
                    {blocks.map((block, index) => {
                    const bbox = block.bbox ?? {};
                    const x1 = safeNumber(bbox.x1);
                    const y1 = safeNumber(bbox.y1);
                    const x2 = safeNumber(bbox.x2);
                    const y2 = safeNumber(bbox.y2);
                    if (x2 <= x1 || y2 <= y1) return null;
                    const key = blockKey(block, index);
                    return (
                      <button
                        aria-label={`${roleLabel(blockRole(block))}识别框`}
                        className={`explain-block ${roleClassName(block)} ${key === selectedBlockKey ? "selected" : ""}`}
                        key={key}
                        style={
                          {
                            left: `${(x1 / pageWidth) * 100}%`,
                            top: `${(y1 / pageHeight) * 100}%`,
                            width: `${((x2 - x1) / pageWidth) * 100}%`,
                            height: `${((y2 - y1) / pageHeight) * 100}%`
                          } as CSSProperties
                        }
                        type="button"
                        onClick={() => setSelectedBlockKey(key)}
                      >
                        {block.order ?? index + 1}
                      </button>
                    );
                  })}
                  </div>
                </div>
              ) : (
                <div className="preview-waiting">
                  <strong>正在渲染页面预览</strong>
                  <span>页面图像生成后，会在这里显示原文和识别框。</span>
                </div>
              )}
            </div>
          </div>

          <div className="preview-footer">
            <div className="legend-row">
              <span className="legend title">标题</span>
              <span className="legend body">正文</span>
              <span className="legend caption">图注/图片</span>
              <span className="legend table">表格</span>
              <span className="legend noise">过滤</span>
            </div>

            <div className="block-inspector">
              <strong>{selectedBlock ? roleLabel(blockRole(selectedBlock)) : "未选择文本块"}</strong>
              {selectedBlock ? (
                <>
                  <span>置信度：{blockConfidence(selectedBlock)}</span>
                  <span>处理结果：{selectedBlock.is_noise ? `已过滤${selectedBlock.noise_reason ? ` · ${selectedBlock.noise_reason}` : ""}` : "保留"}</span>
                  <p>{selectedBlock.text || "该区域暂无 OCR 文本，可能是图片、表格或尚未完成识别。"}</p>
                </>
              ) : (
                <p>点击页面上的识别框，可以查看角色、置信度和清洗原因。</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function TextPane({ bundle, onOpenAi }: { bundle: TaskBundle; onOpenAi: () => void }) {
  const [cleanDocument, setCleanDocument] = useState<CleanDocument | null>(null);
  const [cleanStatus, setCleanStatus] = useState<"loading" | "ready" | "waiting">("loading");
  const [documentSource, setDocumentSource] = useState<"clean" | "edited">("clean");
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [showMedia, setShowMedia] = useState(false);

  useEffect(() => {
    setCleanStatus("loading");
    setIsEditing(false);
    setHasUnsavedChanges(false);
    setEditError(null);
    requestJson<EditableDocumentResponse>(`/api/tasks/${bundle.task.task_id}/edited-document`)
      .then((response) => {
        setCleanDocument(response.document);
        setDocumentSource(response.source);
        setCleanStatus("ready");
      })
      .catch(() => {
        setCleanDocument(null);
        setDocumentSource("clean");
        setCleanStatus("waiting");
      });
  }, [bundle.task.task_id, bundle.task.progress]);

  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [hasUnsavedChanges]);

  const cleanBlocks = cleanBlocksFromDocument(cleanDocument).filter((block) => {
    if (cleanBlockHasMedia(block)) return showMedia || isEditing;
    return Boolean(block.text?.trim());
  });
  const previewBlocks = isEditing ? cleanBlocks : cleanBlocks.slice(0, 40);

  function updateBlockText(block: CleanBlock, index: number, text: string) {
    const key = cleanBlockKey(block, index);
    setCleanDocument((document) => (document ? updateCleanDocumentBlockText(document, key, text) : document));
    setHasUnsavedChanges(true);
    setEditError(null);
  }

  function updateBlockLevel(block: CleanBlock, index: number, value: ParagraphLevelValue) {
    const key = cleanBlockKey(block, index);
    setCleanDocument((document) => (document ? updateCleanDocumentBlockLevel(document, key, value) : document));
    setHasUnsavedChanges(true);
    setEditError(null);
  }

  async function saveEditedDocument() {
    if (!cleanDocument || isSaving) return;
    setIsSaving(true);
    setEditError(null);
    try {
      const response = await requestJson<EditableDocumentResponse>(`/api/tasks/${bundle.task.task_id}/edited-document`, {
        method: "PUT",
        body: JSON.stringify({ document: cleanDocument }),
      });
      setCleanDocument(response.document);
      setDocumentSource(response.source);
      setHasUnsavedChanges(false);
      setIsEditing(false);
    } catch (reason) {
      setEditError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setIsSaving(false);
    }
  }

  async function resetEditedDocument() {
    if (isSaving) return;
    const shouldReset = window.confirm("重置后会放弃当前人工稿，恢复为系统清洗稿。是否继续？");
    if (!shouldReset) return;
    setIsSaving(true);
    setEditError(null);
    try {
      const response = await requestJson<EditableDocumentResponse>(`/api/tasks/${bundle.task.task_id}/edited-document/reset`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setCleanDocument(response.document);
      setDocumentSource(response.source);
      setHasUnsavedChanges(false);
      setIsEditing(false);
    } catch (reason) {
      setEditError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setIsSaving(false);
    }
  }

  function startEditing() {
    if (cleanStatus !== "ready") return;
    setIsEditing(true);
    setShowMedia(true);
    setEditError(null);
  }

  async function cancelEditing() {
    if (hasUnsavedChanges) {
      const shouldDiscard = window.confirm("当前修改尚未保存，是否放弃本次修改？");
      if (!shouldDiscard) return;
      try {
        const response = await requestJson<EditableDocumentResponse>(`/api/tasks/${bundle.task.task_id}/edited-document`);
        setCleanDocument(response.document);
        setDocumentSource(response.source);
      } catch (reason) {
        setEditError(reason instanceof Error ? reason.message : String(reason));
        return;
      }
    }
    setHasUnsavedChanges(false);
    setIsEditing(false);
    setEditError(null);
  }

  return (
    <section className="pane text-pane">
      <div className="pane-title">
        <h2>阅读稿预览</h2>
        <div className="edit-actions">
          {!isEditing ? (
            <button className="edit-action" type="button" onClick={startEditing} disabled={cleanStatus !== "ready"} title="编辑阅读稿">
              <Pencil size={15} />
              <span>编辑</span>
            </button>
          ) : (
            <>
              <button className="edit-action primary" type="button" onClick={saveEditedDocument} disabled={!hasUnsavedChanges || isSaving} title="保存人工稿">
                <Save size={15} />
                <span>{isSaving ? "保存中" : "保存"}</span>
              </button>
              <button className="edit-action" type="button" onClick={cancelEditing} disabled={isSaving} title="退出编辑">
                <X size={15} />
                <span>退出</span>
              </button>
            </>
          )}
          <button className="edit-action" type="button" onClick={resetEditedDocument} disabled={cleanStatus !== "ready" || isSaving || documentSource !== "edited"} title="恢复系统清洗稿">
            <RotateCcw size={15} />
            <span>重置</span>
          </button>
        </div>
        <label className="media-toggle" title="显示图片和表格">
          <input
            type="checkbox"
            checked={showMedia}
            onChange={(e) => setShowMedia(e.target.checked)}
          />
          <span className="media-toggle-track">
            <span className="media-toggle-thumb" />
          </span>
          <span className="media-toggle-label">图片</span>
        </label>
        <span className="live-dot">{cleanStatus === "ready" ? (documentSource === "edited" ? "人工稿" : "已生成") : "实时更新"}</span>
      </div>
      <article className="reading-page">
        {editError && <div className="edit-error">{editError}</div>}
        {hasUnsavedChanges && <div className="edit-unsaved">有未保存修改</div>}
        {cleanStatus !== "ready" && <WaitingReadingPreview task={bundle.task} />}
        {cleanStatus === "ready" && previewBlocks.length === 0 && <p>清洗文档已生成，但正文块为空，请查看 OCR 或清洗报告。</p>}
        {cleanStatus === "ready" &&
          previewBlocks.map((block, index) => {
            if (cleanBlockHasMedia(block) && showMedia) {
              const src = cleanBlockMediaUrl(bundle.task.task_id, block);
              return (
                <div className="media-block" key={`media-${index}`}>
                  {src ? (
                    <div className="media-block-image">
                      <img
                        src={src}
                        alt={block.text || (block.role === "table" ? "表格" : "图片")}
                        loading="lazy"
                      />
                    </div>
                  ) : (
                    <div className="media-missing">媒体素材未生成</div>
                  )}
                  {isEditing ? (
                    <AutoSizeTextarea
                      className="edit-block-input media-caption-input"
                      value={block.text ?? ""}
                      placeholder="补充图片、表格或公式说明"
                      onChange={(event) => {
                        updateBlockText(block, index, event.target.value);
                      }}
                    />
                  ) : (
                    block.text && (
                      <p className={block.type === "caption" || block.role === "caption" ? "media-caption" : ""}>
                        {block.text}
                      </p>
                    )
                  )}
                  {block.role === "table" && !block.is_graphical && (
                    <div className="media-table-marker">
                      <span>表格</span>
                    </div>
                  )}
                </div>
              );
            }
            if (isEditing) {
              return (
                <div className="edit-block-wrap" key={`${block.page_no ?? "p"}-${index}`}>
                  <label className="paragraph-level-control">
                    <span>段落级别</span>
                    <select
                      value={paragraphLevelForBlock(block)}
                      onChange={(event) => updateBlockLevel(block, index, event.target.value as ParagraphLevelValue)}
                    >
                      {PARAGRAPH_LEVEL_OPTIONS.map((option) => (
                        <option value={option.value} key={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <AutoSizeTextarea
                    className={`edit-block-input ${editBlockClassName(block)}`}
                    value={block.text ?? ""}
                    onChange={(event) => {
                      updateBlockText(block, index, event.target.value);
                    }}
                  />
                </div>
              );
            }
            return (
              createElement(
                readingBlockTag(block),
                { className: readingBlockClassName(block), key: `${block.page_no ?? "p"}-${index}` },
                block.text
              )
            );
          })}
      </article>
      <button className="floating-ai" aria-label="打开 AI 导读" onClick={onOpenAi}>
        <AiSparkleIcon size={24} />
      </button>
    </section>
  );
}
function WaitingReadingPreview({ task }: { task: Task }) {
  const currentStage = task.current_stage ? STAGE_LABELS[task.current_stage] ?? task.current_stage : "等待调度";

  return (
    <div className="reading-wait">
      <div className="reading-wait-line" />
      <p>正在把原始页面整理成可阅读的文本稿。</p>
      <p>当前阶段：{currentStage}。完成后，这里会按标题、正文和图片说明展示清洗结果。</p>
      <div className="reading-skeleton" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function FinalDocumentPreview({
  bundle,
  includeMedia,
  onIncludeMediaChange,
}: {
  bundle: TaskBundle;
  includeMedia: boolean;
  onIncludeMediaChange: (value: boolean) => void;
}) {
  const [document, setDocument] = useState<CleanDocument | null>(null);
  const [source, setSource] = useState<"clean" | "edited">("clean");
  const [status, setStatus] = useState<"loading" | "ready" | "waiting">("loading");

  useEffect(() => {
    setStatus("loading");
    requestJson<EditableDocumentResponse>(`/api/tasks/${bundle.task.task_id}/edited-document`)
      .then((response) => {
        setDocument(response.document);
        setSource(response.source);
        setStatus("ready");
      })
      .catch(() => {
        setDocument(null);
        setSource("clean");
        setStatus("waiting");
      });
  }, [bundle.task.task_id, bundle.task.progress]);

  const blocks = cleanBlocksFromDocument(document).filter((block) => {
    if (cleanBlockHasMedia(block)) return includeMedia;
    return Boolean(block.text?.trim());
  });

  return (
    <section className="content-card final-preview-card">
      <div className="final-preview-header">
        <div>
          <h2>最终阅读稿预览</h2>
          <p>这里展示当前保存的阅读稿，下载文件会基于这份内容重新生成。</p>
        </div>
        <div className="final-preview-tools">
          <label className="media-toggle" title="控制预览和导出是否包含图片、表格、公式">
            <input
              type="checkbox"
              checked={includeMedia}
              onChange={(event) => onIncludeMediaChange(event.target.checked)}
            />
            <span className="media-toggle-track">
              <span className="media-toggle-thumb" />
            </span>
            <span className="media-toggle-label">包含图片</span>
          </label>
          <span className="live-dot">{status === "ready" ? (source === "edited" ? "人工稿" : "系统稿") : "读取中"}</span>
        </div>
      </div>
      <article className="reading-page final-reading-page">
        {status !== "ready" && <WaitingReadingPreview task={bundle.task} />}
        {status === "ready" && (
          <>
            {blocks.length === 0 && <p>阅读稿已生成，但正文块为空。</p>}
            {blocks.map((block, index) => {
              if (cleanBlockHasMedia(block)) {
                const src = cleanBlockMediaUrl(bundle.task.task_id, block);
                return (
                  <div className="media-block" key={`final-media-${cleanBlockKey(block, index)}`}>
                    {src ? (
                      <div className="media-block-image">
                        <img
                          src={src}
                          alt={block.text || (block.role === "table" ? "表格" : "图片")}
                          loading="lazy"
                        />
                      </div>
                    ) : (
                      <div className="media-missing">媒体素材未生成</div>
                    )}
                    {block.text && (
                      <p className={block.type === "caption" || block.role === "caption" ? "media-caption" : ""}>
                        {block.text}
                      </p>
                    )}
                  </div>
                );
              }
              return (
                createElement(
                  readingBlockTag(block),
                  { className: readingBlockClassName(block), key: `final-text-${cleanBlockKey(block, index)}` },
                  block.text
                )
              );
            })}
          </>
        )}
      </article>
    </section>
  );
}

function AiPanel({ bundle, onClose }: { bundle: TaskBundle; onClose: () => void }) {
  return (
    <aside className="ai-panel">
      <div className="pane-title">
        <h2>
          <AiSparkleIcon size={18} /> AI 导读
        </h2>
        <button className="icon-button" onClick={onClose} aria-label="关闭 AI 导读">
          <X size={17} />
        </button>
      </div>
      <p className="ai-hint">可以围绕当前识别结果继续追问。</p>
      <div className="prompt-row">
        <button>总结全文</button>
        <button>提炼重点</button>
        <button>解释这段内容</button>
      </div>
      <div className="chat-bubble user">请帮我总结这篇文章的核心观点。</div>
      <div className="chat-bubble">任务 {bundle.task.task_id.slice(0, 8)} 正在构建结构化文本，完成后可生成更稳定的导读。</div>
      <div className="chat-input">
        <input placeholder="输入问题，开始导读..." />
        <button aria-label="发送">
          <MessageSquareText size={17} />
        </button>
      </div>
    </aside>
  );
}

function FinishPanel({ bundle, onBack, onRetry }: { bundle: TaskBundle; onBack: () => void; onRetry: () => void }) {
  const [regenerating, setRegenerating] = useState(false);
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);
  const [includeMedia, setIncludeMedia] = useState(true);
  const exportVariant = includeMedia ? "with-media" : "text-only";

  async function regenerateExports() {
    if (regenerating) return;
    setRegenerating(true);
    try {
      await requestJson<ExportRecord[]>(`/api/tasks/${bundle.task.task_id}/exports/regenerate?include_media=${includeMedia ? "true" : "false"}`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      onRetry();
    } catch {
      window.alert("导出失败，请稍后重试。");
    } finally {
      setRegenerating(false);
    }
  }

  async function generateAndDownload(format: string, mode: "package" | "single" = "package") {
    const downloadKey = `${format}:${mode}:${exportVariant}`;
    if (downloadingFormat) return;
    setDownloadingFormat(downloadKey);
    try {
      const records = await requestJson<ExportRecord[]>(
        `/api/tasks/${bundle.task.task_id}/exports/regenerate?format=${encodeURIComponent(format)}&include_media=${includeMedia ? "true" : "false"}`,
        {
          method: "POST",
          body: JSON.stringify({}),
        }
      );
      const latest = [...records].reverse().find((record) =>
        record.format.toLowerCase() === format && Boolean(record.file_path?.includes(exportVariant))
      ) ?? [...records].reverse().find((record) => record.format.toLowerCase() === format);
      if (!latest) throw new Error("导出文件未生成");
      onRetry();
      const modeQuery = ["markdown", "html"].includes(format) && mode === "single" ? "?mode=single" : "";
      window.open(`${API_BASE}/api/exports/${latest.id}/download${modeQuery}`, "_blank", "noopener,noreferrer");
    } catch {
      window.alert("下载前生成最新文件失败，请稍后重试。");
    } finally {
      setDownloadingFormat(null);
    }
  }

  return (
    <section className="finish-screen">
      <div className="success-panel">
        <span className="success-mark">
          <CheckCircleIcon size={46} />
        </span>
        <h1>你的文档已准备就绪</h1>
        <p className="success-filename">{bundle.task.original_name}</p>
        <div className="success-meta">
          <span className="success-meta-item">
            <ProgressClockIcon size={14} /> {formatTime(bundle.task.finished_at)}
          </span>
          <span className="success-meta-divider" />
          <span className="success-meta-item">{bundle.task.page_count ?? '-'} 页</span>
        </div>
      </div>

      <section className="export-section">
        <div className="export-header">
          <h2>导出文件</h2>
          <span className="export-count">{includeMedia ? "包含图片" : "仅文字"} · {bundle.exports.length} 个文件</span>
        </div>
        <div className="export-grid">
          {(() => {
            const allFormats = [
              { key: 'epub', label: 'EPUB', icon: FileText, previewable: false },
              { key: 'docx', label: 'DOCX', icon: FileText, previewable: false },
              { key: 'markdown', label: 'Markdown', icon: FileCode2, previewable: true },
              { key: 'html', label: 'HTML', icon: FileCode2, previewable: true },
            ];
            return allFormats.map((fmt) => {
              const match = [...bundle.exports].reverse().find((e) =>
                e.format.toLowerCase() === fmt.key && Boolean(e.file_path?.includes(exportVariant))
              );
              const packageDownloadKey = `${fmt.key}:package:${exportVariant}`;
              const singleDownloadKey = `${fmt.key}:single:${exportVariant}`;
              const isPackageDownloading = downloadingFormat === packageDownloadKey;
              const isSingleDownloading = downloadingFormat === singleDownloadKey;
              const canDownloadSingleFile = ["markdown", "html"].includes(fmt.key);

              return (
                <div
                  className="export-card"
                  key={fmt.key}
                >
                  <div className="export-card-icon">
                    <fmt.icon size={20} />
                  </div>
                  <span className="export-card-label">{fmt.label}</span>
                  <span className="export-card-size">{isPackageDownloading || isSingleDownloading ? "正在生成最新文件" : match ? formatSize(match.file_size) : "点击生成"}</span>
                  <button
                    className="export-card-action"
                    type="button"
                    disabled={downloadingFormat !== null || regenerating}
                    title={canDownloadSingleFile ? "下载资源包" : "基于当前阅读稿生成并下载"}
                    onClick={(event) => {
                      event.stopPropagation();
                      generateAndDownload(fmt.key, "package");
                    }}
                  >
                    {isPackageDownloading ? <RefreshCw size={14} /> : <DownloadIcon size={14} />}
                  </button>
                  {canDownloadSingleFile && (
                    <button
                      className="export-card-single-action"
                      type="button"
                      disabled={downloadingFormat !== null || regenerating}
                      title="单文件下载，图片会以内嵌 base64 保存"
                      onClick={(event) => {
                        event.stopPropagation();
                        generateAndDownload(fmt.key, "single");
                      }}
                    >
                      {isSingleDownloading ? "生成中" : "单文件"}
                    </button>
                  )}
                </div>
              );
            });
          })()}
        </div>
      </section>

      <FinalDocumentPreview bundle={bundle} includeMedia={includeMedia} onIncludeMediaChange={setIncludeMedia} />

      <div className="finish-actions">
        <button className="secondary-button" onClick={onBack}>
          返回首页
        </button>
        <button className="secondary-button" onClick={regenerateExports} disabled={regenerating}>
          <RefreshCw size={17} />
          {regenerating ? "导出中" : "重新导出最终稿"}
        </button>
        <button className="primary-button" onClick={onRetry}>
          <RefreshCw size={17} />
          刷新结果
        </button>
      </div>
    </section>
  );
}
function StatusBadge({ status }: { status: string }) {
  const text = status === "success" ? "成功" : status === "failed" ? "失败" : status === "processing" ? "处理中" : "等待";
  return <span className={`status-badge ${status}`}>{text}</span>;
}
