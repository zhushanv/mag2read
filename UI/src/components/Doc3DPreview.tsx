 // @ts-nocheck
 import { useMemo } from "react";
 import { Canvas, useThree } from "@react-three/fiber";
 import { OrbitControls, Html } from "@react-three/drei";
 import * as THREE from "three";
 
 type Block3D = {
   id: string;
   type: string;
   x: number;
   y: number;
   width: number;
   height: number;
   pageNo: number;
   confidence: number;
   isNoise: boolean;
 };
 
 type PageData = {
   pageNo: number;
   width: number;
   height: number;
   blocks: Array<{
     block_id?: string;
     id?: string | number;
     type?: string;
     role?: string;
     text?: string;
     bbox?: { x1?: number; y1?: number; x2?: number; y2?: number };
     ocr_confidence?: number | null;
     is_noise?: boolean;
   }>;
 };
 
 type Doc3DPreviewProps = {
   pages: PageData[];
 };
 
 const TYPE_COLORS: Record<string, string> = {
   title: "#3084ff",
   heading: "#4a9eff",
   paragraph: "#e8edf4",
   body: "#e8edf4",
   caption: "#60d8a0",
   figure: "#60d8a0",
   image: "#60d8a0",
   table: "#f0a040",
   noise: "#e74c3c",
   header: "#e74c3c",
   footer: "#e74c3c",
   page_number: "#e74c3c",
   default: "#889ab0",
 };
 
 function getBlockType(block: PageData["blocks"][0]): string {
   const role = block.role ?? block.type ?? "unknown";
   if (block.is_noise) return "noise";
   if (["title", "heading"].includes(role)) return "title";
   if (["caption", "figure", "image"].includes(role)) return "caption";
   if (role === "table") return "table";
   if (role === "page_number") return "page_number";
   return role;
 }
 
 function Blocks({ blocks, maxWidth, maxHeight }: { blocks: Block3D[]; maxWidth: number; maxHeight: number }) {
   const { camera } = useThree();
   useMemo(() => {
     const totalPages = Math.max(...blocks.map((b) => b.pageNo), 1);
     const centerZ = (totalPages - 1) * 2.5 / 2;
     camera.position.set(maxWidth * 0.6, -maxHeight * 0.3, centerZ + 6);
     camera.lookAt(maxWidth / 2, -maxHeight / 2, centerZ);
   }, [blocks, maxWidth, maxHeight]);
 
   return blocks.map((block) => {
     const color = TYPE_COLORS[block.type] ?? TYPE_COLORS.default;
     const hexColor = new THREE.Color(color);
     const opacity = block.isNoise ? 0.3 : 0.4 + 0.6 * block.confidence;
 
     return (
       <mesh
         key={block.id}
         position={[
           block.x + block.width / 2,
           -(block.y + block.height / 2),
           block.pageNo * 2.5,
         ]}
       >
         <planeGeometry args={[Math.max(block.width, 1), Math.max(block.height, 1)]} />
         <meshStandardMaterial
           color={hexColor}
           transparent
           opacity={opacity}
           roughness={0.3}
           metalness={0.1}
         />
         <Html distanceFactor={120} style={{ display: "none" }} />
       </mesh>
     );
   });
 }
 
 function PagePlanes({ pageCount, maxWidth, maxHeight }: { pageCount: number; maxWidth: number; maxHeight: number }) {
   return Array.from({ length: pageCount }, (_, i) => (
     <mesh key={`page-${i}`} position={[maxWidth / 2, -maxHeight / 2, i * 2.5]}>
       <planeGeometry args={[maxWidth + 2, maxHeight + 2]} />
       <meshBasicMaterial color="#f0f4fa" transparent opacity={0.08} side={THREE.DoubleSide} />
     </mesh>
   ));
 }
 
 function Scene({ pages }: { pages: PageData[] }) {
   const blocks = useMemo(() => {
     const result: Block3D[] = [];
     pages.forEach((page) => {
       (page.blocks ?? []).forEach((block, idx) => {
         const bbox = block.bbox ?? {};
         const x = bbox.x1 ?? 0;
         const y = bbox.y1 ?? 0;
         const w = (bbox.x2 ?? page.width) - x;
         const h = (bbox.y2 ?? page.height) - y;
         const confidence = block.ocr_confidence ?? 0.5;
         result.push({
           id: String(block.block_id ?? block.id ?? `b-${page.pageNo}-${idx}`),
           x, y, width: w, height: h,
           pageNo: page.pageNo,
           type: getBlockType(block),
           confidence: typeof confidence === "number" ? Math.min(confidence, 1) : 0.5,
           isNoise: !!block.is_noise,
         });
       });
     });
     return result;
   }, [pages]);
 
   const maxWidth = Math.max(...pages.map((p) => p.width), 800);
   const maxHeight = Math.max(...pages.map((p) => p.height), 1000);
 
   return (
     <>
       <ambientLight intensity={0.6} />
       <directionalLight position={[5, 5, 5]} intensity={0.8} />
       <directionalLight position={[-3, 2, -3]} intensity={0.3} />
       <Blocks blocks={blocks} maxWidth={maxWidth} maxHeight={maxHeight} />
       <PagePlanes pageCount={pages.length} maxWidth={maxWidth} maxHeight={maxHeight} />
       <OrbitControls
         enableDamping
         dampingFactor={0.1}
         minDistance={2}
         maxDistance={20}
       />
     </>
   );
 }
 
 export default function Doc3DPreview({ pages }: Doc3DPreviewProps) {
   if (pages.length === 0) return <div className="doc-3d-empty">暂无页面数据</div>;
 
   return (
     <div className="doc-3d-container">
       <div className="doc-3d-legend">
         <span><span className="legend-dot" style={{ background: "#3084ff" }} /> 标题</span>
         <span><span className="legend-dot" style={{ background: "#e8edf4" }} /> 正文</span>
         <span><span className="legend-dot" style={{ background: "#60d8a0" }} /> 图片/表格</span>
         <span><span className="legend-dot" style={{ background: "#f0a040" }} /> 表格</span>
         <span><span className="legend-dot" style={{ background: "#e74c3c" }} /> 页眉/页脚</span>
       </div>
       <Canvas
         dpr={[0.5, 1]}
         gl={{ antialias: true, alpha: true }}
         style={{ width: "100%", height: "100%", background: "transparent" }}
       >
         <Scene pages={pages} />
       </Canvas>
     </div>
   );
 }
