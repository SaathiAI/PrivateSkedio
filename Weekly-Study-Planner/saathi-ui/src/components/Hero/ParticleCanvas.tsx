import { Canvas, useThree } from "@react-three/fiber";
import { AdaptiveDpr, PerformanceMonitor } from "@react-three/drei";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useRef, useState } from "react";
import type { MutableRefObject } from "react";
import type { AnimationTimeline } from "./useAnimationTimeline";
import { ParticleSystem } from "./ParticleSystem";
import { OuterSphere } from "./OuterSphere";
import { HudElements } from "./HudElements";

type Props = {
  timeline: AnimationTimeline;
  particleCount: number;
  pointSize: number;
  bloom: number;
};

export function ParticleCanvas({ timeline, particleCount, pointSize, bloom }: Props) {
  const pointer = useRef<[number, number]>([0, 0]);
  const [dpr, setDpr] = useState(1.5);

  return (
    <div
      className="hero-canvas"
      aria-hidden="true"
      onPointerMove={(event) => {
        if (timeline.reducedMotion || event.pointerType === "touch") return;
        pointer.current = [event.clientX / window.innerWidth - 0.5, 0.5 - event.clientY / window.innerHeight];
      }}
      onPointerLeave={() => { pointer.current = [0, 0]; }}
    >
      <Canvas
        dpr={dpr}
        camera={{ position: [0, 0, 9], fov: 46, near: 0.1, far: 40 }}
        gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
      >
        <PerformanceMonitor
          flipflops={3}
          onIncline={() => setDpr((value) => Math.min(1.75, value + 0.15))}
          onDecline={() => setDpr((value) => Math.max(0.85, value - 0.2))}
        />
        <AdaptiveDpr pixelated />
        <OuterSphere timeline={timeline} />
        <ResponsiveParticles timeline={timeline} particleCount={particleCount} pointSize={pointSize} pointer={pointer} />
        {bloom > 0 ? (
          <EffectComposer multisampling={0}>
            <Bloom intensity={bloom} luminanceThreshold={0.92} luminanceSmoothing={0.08} mipmapBlur />
          </EffectComposer>
        ) : null}
      </Canvas>
    </div>
  );
}

function ResponsiveParticles({ timeline, particleCount, pointSize, pointer }: Omit<Props, "bloom"> & { pointer: MutableRefObject<[number, number]> }) {
  const viewport = useThree((state) => state.viewport);
  const sceneScale = Math.min(1, viewport.width / 9.7);
  return (
    <group scale={sceneScale}>
      <ParticleSystem count={particleCount} pointSize={pointSize} timeline={timeline} pointer={pointer} />
      <HudElements timeline={timeline} />
    </group>
  );
}
