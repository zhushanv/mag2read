 import { useEffect, useRef, useState } from "react";
 
 /** 从 0 → end 的递增计数动画，duration 毫秒 */
 export function useCountUp(end: number, duration = 1000, enabled = true) {
   const [value, setValue] = useState(0);
   const rafRef = useRef<number>(0);
   const startRef = useRef<number>(0);
 
   useEffect(() => {
     if (!enabled) { setValue(end); return; }
     if (end === 0) { setValue(0); return; }
 
     startRef.current = performance.now();
 
     const tick = (now: number) => {
       const elapsed = now - startRef.current;
       const progress = Math.min(elapsed / duration, 1);
       // ease-out cubic
       const eased = 1 - Math.pow(1 - progress, 3);
       setValue(Math.round(eased * end));
       if (progress < 1) rafRef.current = requestAnimationFrame(tick);
     };
 
     rafRef.current = requestAnimationFrame(tick);
     return () => cancelAnimationFrame(rafRef.current);
   }, [end, duration, enabled]);
 
   return value;
 }
