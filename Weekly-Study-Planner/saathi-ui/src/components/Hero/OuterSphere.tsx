import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { mulberry32 } from "../../utils/seededRandom";
import type { AnimationTimeline } from "./useAnimationTimeline";

export function OuterSphere({ timeline }: { timeline: AnimationTimeline }) {
  const pointsRef = useRef<THREE.Points>(null);
  const materialRef = useRef<THREE.PointsMaterial>(null);
  const geometry = useMemo(() => {
    const random = mulberry32(57022);
    const positions: number[] = [];
    for (let index = 0; index < 6200; index += 1) {
      const theta = random() * Math.PI * 2;
      const phi = Math.acos(2 * random() - 1);
      const sideWeight = Math.abs(Math.cos(theta));
      if (sideWeight < 0.58 || random() < 0.23 + Math.sin(index * 1.71) * 0.16) continue;
      const radius = 6.35 + (random() - 0.5) * 0.12;
      positions.push(
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi) * 0.92 - 0.3,
        radius * Math.sin(phi) * Math.sin(theta) * 0.48,
      );
    }
    const next = new THREE.BufferGeometry();
    next.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    return next;
  }, []);

  useEffect(() => () => geometry.dispose(), [geometry]);

  useFrame(({ clock }) => {
    if (pointsRef.current && !timeline.reducedMotion) {
      pointsRef.current.rotation.y = Math.sin(clock.elapsedTime * 0.055) * 0.035;
      pointsRef.current.rotation.z = Math.sin(clock.elapsedTime * 0.038) * 0.012;
    }
    if (materialRef.current) {
      const p = timeline.progress;
      const centralIsDark = p > 0.25 && p < 0.5;
      materialRef.current.opacity = centralIsDark ? 0.28 : 0.16;
    }
  });

  return (
    <points ref={pointsRef} geometry={geometry} frustumCulled={false}>
      <pointsMaterial
        ref={materialRef}
        color="#c9ebff"
        size={0.018}
        sizeAttenuation
        transparent
        opacity={0.18}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}
