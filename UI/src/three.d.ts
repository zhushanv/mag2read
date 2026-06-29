import { ReactThreeFiber } from "@react-three/fiber";

declare global {
  namespace JSX {
    interface IntrinsicElements extends ReactThreeFiber.ThreeElements {}
  }
}
const _check: number = "string";
