import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import type { AnimationTimeline } from "./useAnimationTimeline";

function dottedRing(radius: number, count: number, arc = Math.PI * 2) {
  const positions: number[] = [];
  for (let index = 0; index < count; index += 1) {
    if (index % 4 === 1) continue;
    const angle = (index / count) * arc;
    positions.push(Math.cos(angle) * radius, Math.sin(angle) * radius, 0);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  return geometry;
}

export function HudElements({ timeline }: { timeline: AnimationTimeline }) {
  const groupRef = useRef<THREE.Group>(null);
  const targetRef = useRef<THREE.PointsMaterial>(null);
  const rightRing = useMemo(() => dottedRing(0.72, 92), []);
  const targetRing = useMemo(() => dottedRing(0.18, 42), []);

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    const p = timeline.progress;
    const reconstruction = THREE.MathUtils.smoothstep(p, 0.68, 0.79);
    const fading = 1 - THREE.MathUtils.smoothstep(p, 0.25, 0.38);
    const visible = p < 0.38 ? fading : p < 0.68 ? 0.13 : reconstruction;
    groupRef.current.children.forEach((child) => {
      const material = (child as THREE.Points).material as THREE.PointsMaterial;
      if (material?.opacity !== undefined) material.opacity = visible * 0.56;
    });
    groupRef.current.rotation.z = timeline.reducedMotion ? 0 : clock.elapsedTime * 0.012;
    if (targetRef.current) targetRef.current.opacity = 0.42 + Math.sin(clock.elapsedTime * 2.3) * 0.14;
  });

  return (
    <>
      <group ref={groupRef} position={[3.7, -0.65, -0.25]}>
        <points geometry={rightRing}>
          <pointsMaterial color="#cfefff" size={0.028} transparent opacity={0.35} depthWrite={false} />
        </points>
      </group>
      <points geometry={targetRing} position={[0.25, -0.62, 1.1]}>
        <pointsMaterial ref={targetRef} color="#78eeff" size={0.034} transparent opacity={0.5} depthWrite={false} />
      </points>
    </>
  );
}
