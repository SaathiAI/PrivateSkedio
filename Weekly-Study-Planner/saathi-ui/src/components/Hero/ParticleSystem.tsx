import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import type { MutableRefObject } from "react";
import * as THREE from "three";
import particleVertexShader from "./shaders/particle.vert.glsl?raw";
import particleFragmentShader from "./shaders/particle.frag.glsl?raw";
import type { AnimationTimeline } from "./useAnimationTimeline";
import { mulberry32, randomDirection } from "../../utils/seededRandom";

type Props = {
  count: number;
  pointSize: number;
  timeline: AnimationTimeline;
  pointer: MutableRefObject<[number, number]>;
};

function createParticleData(count: number) {
  const random = mulberry32(271904);
  const final = new Float32Array(count * 3);
  const seed = new Float32Array(count * 3);
  const burst = new Float32Array(count * 3);
  const direction = new Float32Array(count * 3);
  const phase = new Float32Array(count);
  const scale = new Float32Array(count);
  const brightness = new Float32Array(count);
  const group = new Float32Array(count);
  const trail = new Float32Array(count);

  for (let index = 0; index < count; index += 1) {
    const offset = index * 3;
    const band = Math.floor(random() * 13);
    const normalizedBand = band / 12;
    const yBase = (normalizedBand - 0.5) * 2.15;
    const envelope = Math.pow(Math.max(0.04, 1 - Math.pow(yBase / 1.28, 2)), 0.42);
    let x = (random() * 2 - 1) * 4.15 * envelope;
    let y = yBase + (random() - 0.5) * (0.07 + random() * 0.055);
    const gap = Math.sin(x * 1.7 + band * 2.3) + Math.sin(x * 0.52 - band * 0.9);
    if (gap > 1.35 && random() < 0.82) x *= 0.72 + random() * 0.18;
    if (random() < 0.09) {
      x *= 1.1 + random() * 0.24;
      y += (random() - 0.5) * 0.34;
    }
    const zEnvelope = Math.sqrt(Math.max(0, 1 - Math.min(0.98, (x / 4.7) ** 2)));
    const z = (random() * 2 - 1) * (0.22 + zEnvelope * 0.72);
    const dir = randomDirection(random);
    const seedRadius = Math.pow(random(), 1.8) * 0.42;
    const burstRadius = 1.5 + Math.pow(random(), 0.48) * 5.4;
    const horizontalBias = 1.2 + random() * 1.45;

    final[offset] = x;
    final[offset + 1] = y - 0.7;
    final[offset + 2] = z;
    seed[offset] = dir[0] * seedRadius;
    seed[offset + 1] = dir[1] * seedRadius - 0.58;
    seed[offset + 2] = dir[2] * seedRadius;
    burst[offset] = dir[0] * burstRadius * horizontalBias;
    burst[offset + 1] = dir[1] * burstRadius * 0.52 - 0.62;
    burst[offset + 2] = dir[2] * burstRadius * 0.82;
    direction[offset] = dir[0];
    direction[offset + 1] = dir[1];
    direction[offset + 2] = dir[2];
    phase[index] = random() * Math.PI * 2;
    scale[index] = 0.62 + random() * 1.45;
    brightness[index] = 0.25 + Math.pow(random(), 0.72) * 0.75;
    group[index] = (band + random() * 0.8) / 12.8;
    trail[index] = Math.pow(random(), 2.7);
  }

  return { final, seed, burst, direction, phase, scale, brightness, group, trail };
}

export function ParticleSystem({ count, pointSize, timeline, pointer }: Props) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const geometry = useMemo(() => {
    const data = createParticleData(count);
    const next = new THREE.BufferGeometry();
    next.setAttribute("position", new THREE.BufferAttribute(data.final, 3));
    next.setAttribute("aFinal", new THREE.BufferAttribute(data.final, 3));
    next.setAttribute("aSeed", new THREE.BufferAttribute(data.seed, 3));
    next.setAttribute("aBurst", new THREE.BufferAttribute(data.burst, 3));
    next.setAttribute("aDirection", new THREE.BufferAttribute(data.direction, 3));
    next.setAttribute("aPhase", new THREE.BufferAttribute(data.phase, 1));
    next.setAttribute("aScale", new THREE.BufferAttribute(data.scale, 1));
    next.setAttribute("aBrightness", new THREE.BufferAttribute(data.brightness, 1));
    next.setAttribute("aGroup", new THREE.BufferAttribute(data.group, 1));
    next.setAttribute("aTrail", new THREE.BufferAttribute(data.trail, 1));
    next.computeBoundingSphere();
    return next;
  }, [count]);

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uProgress: { value: 0 },
    uPixelRatio: { value: Math.min(window.devicePixelRatio, 1.75) },
    uPointSize: { value: pointSize },
    uReducedMotion: { value: 0 },
    uMouse: { value: new THREE.Vector2() },
  }), []);

  useEffect(() => () => geometry.dispose(), [geometry]);

  useFrame(({ clock }) => {
    if (!materialRef.current) return;
    const values = materialRef.current.uniforms;
    values.uTime.value = clock.elapsedTime;
    values.uProgress.value = timeline.progress;
    values.uPointSize.value = pointSize;
    values.uReducedMotion.value = timeline.reducedMotion ? 1 : 0;
    values.uMouse.value.set(pointer.current[0], pointer.current[1]);
  });

  return (
    <points geometry={geometry} frustumCulled={false}>
      <shaderMaterial
        ref={materialRef}
        uniforms={uniforms}
        vertexShader={particleVertexShader}
        fragmentShader={particleFragmentShader}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}
