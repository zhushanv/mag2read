// @ts-nocheck
import { useRef, useMemo } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

const vertexShader = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const fragmentShader = `
uniform vec2 uResolution;
uniform float uTime;
uniform vec2 uMouse;
uniform float uDpr;
varying vec2 vUv;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

void main() {
  vec2 uv = gl_FragCoord.xy / (uResolution * uDpr);
  float aspect = uResolution.x / uResolution.y;
  vec2 p = uv * 2.0 - 1.0;
  p.x *= aspect;

  vec2 mp = (uMouse * 2.0 - 1.0) * 0.22;
  vec2 pos = p + mp;

  float t = uTime * 0.26;
  float n1 = noise(pos * 1.22 + vec2(t * 1.22, -t * 0.56));
  float n2 = noise(pos * 2.25 - vec2(t * 0.92, t * 0.48) + vec2(1.2));
  float n3 = noise(pos * 4.0 + vec2(t * 0.56, -t * 0.98) + vec2(2.3, 0.7));

  float ribbonA = smoothstep(0.64, 0.04, abs(pos.y + 0.32 * sin(pos.x * 2.2 + t * 4.4) - 0.08));
  float ribbonB = smoothstep(0.58, 0.06, abs(pos.y - 0.34 * sin(pos.x * 1.45 - t * 3.7) + 0.2));
  float ribbonC = smoothstep(0.48, 0.07, abs(pos.x + 0.18 * sin(pos.y * 2.8 + t * 3.1) - 0.36));

  float blend = (n1 * 0.6 + n2 * 0.3 + n3 * 0.1);
  blend = smoothstep(0.25, 0.75, blend);

  vec3 c1 = vec3(0.50, 0.78, 1.0);
  vec3 c2 = vec3(0.92, 0.98, 1.0);
  vec3 c3 = vec3(0.44, 0.94, 0.86);
  vec3 c4 = vec3(1.0, 0.86, 0.72);
  vec3 ink = vec3(0.24, 0.45, 0.86);

  vec3 color = mix(c1, c2, blend);
  color = mix(color, c3, smoothstep(0.2, 0.8, n2));
  color = mix(color, c4, smoothstep(0.3, 0.7, n3));
  color = mix(color, ink, ribbonA * 0.22);
  color = mix(color, c3, ribbonB * 0.34);
  color = mix(color, c4, ribbonC * 0.2);

  float alpha = 0.66 + 0.18 * blend + ribbonA * 0.1 + ribbonB * 0.08 + ribbonC * 0.06;
  gl_FragColor = vec4(color, alpha);
}
`;

type FluidShaderUniforms = {
  uResolution: { value: THREE.Vector2 };
  uTime: { value: number };
  uMouse: { value: THREE.Vector2 };
  uDpr: { value: number };
};

function FluidPlane() {
  const meshRef = useRef<THREE.Mesh>(null);
  const { size, viewport, gl } = useThree();
  const frameSkip = useRef(0);

  const uniforms = useMemo<FluidShaderUniforms>(() => ({
    uResolution: { value: new THREE.Vector2(size.width, size.height) },
    uTime: { value: 0 },
    uMouse: { value: new THREE.Vector2(0.5, 0.4) },
    uDpr: { value: gl.getPixelRatio() },
  }), []);

  useFrame((state) => {
    // Update every 6th frame (~10fps instead of 60fps) to save CPU
    frameSkip.current = (frameSkip.current + 1) % 6;
    if (frameSkip.current !== 0) return;
    uniforms.uTime.value = state.clock.elapsedTime;
    const w = size.width;
    const h = size.height;
    if (uniforms.uResolution.value.x !== w || uniforms.uResolution.value.y !== h) {
      uniforms.uResolution.value.set(w, h);
    }
    uniforms.uDpr.value = gl.getPixelRatio();
  });

  return (
    <mesh ref={meshRef} scale={[viewport.width, viewport.height, 1]}>
      <planeGeometry args={[1, 1]} />
      <shaderMaterial
        fragmentShader={fragmentShader}
        vertexShader={vertexShader}
        uniforms={uniforms}
        transparent
        depthWrite={false}
      />
    </mesh>
  );
}

export default function FluidBackground() {
  return (
    <div className="fluid-background">
      <Canvas
        dpr={[0.25, 0.5]}
        gl={{ antialias: false, alpha: true, powerPreference: "low-power" }}
        frameloop="demand"
        style={{ width: "100%", height: "100%" }}
      >
        <FluidPlane />
      </Canvas>
    </div>
  );
}
