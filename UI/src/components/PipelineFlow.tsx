 // @ts-nocheck
 import { Check, RefreshCw } from "lucide-react";
 
 const STAGE_LABELS: Record<string, string> = {
   render: "页面渲染",
   layout_detect: "版面分析",
   layout_refine: "规则清洗",
   ocr: "文字识别",
   text_cleaning: "文本整理",
   document_build: "结构构建",
   export: "文件导出",
 };
 
 type PipelineFlowProps = {
   stages: string[];
   stepMap: Map<string, { status: string; progress: number }>;
   currentStage: string | null;
 };
 
 export default function PipelineFlow({ stages, stepMap, currentStage }: PipelineFlowProps) {
   const activeIdx = currentStage ? stages.indexOf(currentStage) : -1;
 
   return (
     <div className="pipeline-flow">
       {stages.map((stage, idx) => {
         const step = stepMap.get(stage);
         const status = getStatus(step, stage, currentStage);
         const isDone = status === "done";
         const isActive = status === "active";
         const isLast = idx === stages.length - 1;
 
         return (
           <div key={stage} className={`pipeline-node ${status}`}>
             {!isLast && (
               <div className={`pipeline-line ${isDone ? "done" : ""}`}>
                 <span className="pipeline-flow-dot" />
               </div>
             )}
             <div className="pipeline-icon">
               {isDone ? <Check size={16} /> : isActive ? <RefreshCw size={15} className="pulse" /> : <span className="dot" />}
             </div>
             <div className="pipeline-label">{STAGE_LABELS[stage]}</div>
             <div className="pipeline-progress-text">{isDone ? "✓" : isActive ? `${step?.progress ?? 0}%` : ""}</div>
           </div>
         );
       })}
     </div>
   );
 }
 
 function getStatus(
   step: { status: string; progress: number } | undefined,
   stage: string,
   currentStage: string | null
 ): "done" | "active" | "failed" | "wait" {
   if (step?.status === "success") return "done";
   if (step?.status === "failed") return "failed";
   if (currentStage === stage || step?.status === "processing") return "active";
   return "wait";
 }
