 import { useCountUp } from "../hooks/useCountUp";
 
 type CountUpProps = {
   end: number;
   duration?: number;
   suffix?: string;
   enabled?: boolean;
 };
 
 export function CountUp({ end, duration = 1000, suffix = "", enabled = true }: CountUpProps) {
   const value = useCountUp(end, duration, enabled);
   return <span className="count-up-value">{value}{suffix}</span>;
 }
