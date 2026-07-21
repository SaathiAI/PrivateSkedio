import { useEffect, useRef } from "react";

export const LOOP_DURATION = 7_000;

export type TimelineSnapshot = {
  progress: number;
  elapsed: number;
  phase: string;
  paused: boolean;
  reducedMotion: boolean;
};

const phases = [
  [0, 1.8 / 7, "Ambient"],
  [1.8 / 7, 2.7 / 7, "Dissolution"],
  [2.7 / 7, 3.15 / 7, "Scanning field"],
  [3.15 / 7, 3.65 / 7, "Seed formation"],
  [3.65 / 7, 4.35 / 7, "Expansion"],
  [4.35 / 7, 5.55 / 7, "Reconstruction"],
  [5.55 / 7, 1.001, "Settled"],
] as const;

export function phaseForProgress(progress: number) {
  return phases.find(([, end]) => progress < end)?.[2] ?? "Settled";
}

export class AnimationTimeline {
  progress = 0;
  speed = 1;
  paused = false;
  reducedMotion = false;
  private elapsed = 0;
  private previousTime = 0;
  private listeners = new Set<(snapshot: TimelineSnapshot) => void>();

  tick = (now: number) => {
    if (!this.previousTime) this.previousTime = now;
    const delta = Math.min(now - this.previousTime, 100);
    this.previousTime = now;

    if (this.reducedMotion) {
      this.progress = 0.9;
    } else if (!this.paused) {
      this.elapsed = (this.elapsed + delta * this.speed) % LOOP_DURATION;
      this.progress = this.elapsed / LOOP_DURATION;
    }

    const snapshot = this.snapshot();
    this.listeners.forEach((listener) => listener(snapshot));
  };

  setProgress(progress: number) {
    this.progress = Math.min(0.9999, Math.max(0, progress));
    this.elapsed = this.progress * LOOP_DURATION;
    const snapshot = this.snapshot();
    this.listeners.forEach((listener) => listener(snapshot));
  }

  setPaused(paused: boolean) {
    this.paused = paused;
    this.previousTime = performance.now();
  }

  resetClock() {
    this.previousTime = performance.now();
  }

  subscribe(listener: (snapshot: TimelineSnapshot) => void) {
    this.listeners.add(listener);
    listener(this.snapshot());
    return () => { this.listeners.delete(listener); };
  }

  snapshot(): TimelineSnapshot {
    return {
      progress: this.progress,
      elapsed: this.progress * LOOP_DURATION,
      phase: phaseForProgress(this.progress),
      paused: this.paused,
      reducedMotion: this.reducedMotion,
    };
  }
}

export function useAnimationTimeline() {
  const timelineRef = useRef<AnimationTimeline | null>(null);
  if (!timelineRef.current) timelineRef.current = new AnimationTimeline();

  useEffect(() => {
    const timeline = timelineRef.current!;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let visible = !document.hidden;

    const updateMotionPreference = () => {
      timeline.reducedMotion = media.matches;
      timeline.resetClock();
    };
    const updateVisibility = () => {
      visible = !document.hidden;
      timeline.resetClock();
      if (visible) frame = requestAnimationFrame(loop);
    };
    const loop = (now: number) => {
      timeline.tick(now);
      if (visible) frame = requestAnimationFrame(loop);
    };

    updateMotionPreference();
    media.addEventListener("change", updateMotionPreference);
    document.addEventListener("visibilitychange", updateVisibility);
    frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      media.removeEventListener("change", updateMotionPreference);
      document.removeEventListener("visibilitychange", updateVisibility);
    };
  }, []);

  return timelineRef.current;
}
