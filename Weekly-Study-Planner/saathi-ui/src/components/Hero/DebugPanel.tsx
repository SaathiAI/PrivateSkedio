import { useEffect, useState } from "react";
import type { AnimationTimeline, TimelineSnapshot } from "./useAnimationTimeline";

type Props = {
  timeline: AnimationTimeline;
  particleCount: number;
  pointSize: number;
  bloom: number;
  onParticleCount: (value: number) => void;
  onPointSize: (value: number) => void;
  onBloom: (value: number) => void;
};

export function DebugPanel(props: Props) {
  const [open, setOpen] = useState(false);
  const [snapshot, setSnapshot] = useState<TimelineSnapshot>(() => props.timeline.snapshot());

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "d" && !event.metaKey && !event.ctrlKey) setOpen((value) => !value);
    };
    window.addEventListener("keydown", onKey);
    const timer = window.setInterval(() => setSnapshot(props.timeline.snapshot()), 100);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.clearInterval(timer);
    };
  }, [props.timeline]);

  if (!import.meta.env.DEV || !open) return null;

  return (
    <aside className="hero-debug" aria-label="Hero animation debug panel">
      <div className="debug-heading"><strong>Motion lab</strong><span>{snapshot.phase}</span></div>
      <label>Timeline <output>{snapshot.elapsed.toFixed(0)} ms</output>
        <input type="range" min="0" max="0.999" step="0.001" value={snapshot.progress} onChange={(e) => props.timeline.setProgress(Number(e.target.value))} />
      </label>
      <label>Particles <output>{props.particleCount.toLocaleString()}</output>
        <input type="range" min="12000" max="60000" step="2000" value={props.particleCount} onChange={(e) => props.onParticleCount(Number(e.target.value))} />
      </label>
      <label>Point size <output>{props.pointSize.toFixed(1)}</output>
        <input type="range" min="1" max="4" step="0.1" value={props.pointSize} onChange={(e) => props.onPointSize(Number(e.target.value))} />
      </label>
      <label>Bloom <output>{props.bloom.toFixed(2)}</output>
        <input type="range" min="0" max="1" step="0.05" value={props.bloom} onChange={(e) => props.onBloom(Number(e.target.value))} />
      </label>
      <label>Speed <output>{props.timeline.speed.toFixed(1)}×</output>
        <input type="range" min="0.25" max="2" step="0.25" defaultValue={props.timeline.speed} onChange={(e) => { props.timeline.speed = Number(e.target.value); }} />
      </label>
      <button type="button" onClick={() => props.timeline.setPaused(!props.timeline.paused)}>{snapshot.paused ? "Play" : "Pause"}</button>
    </aside>
  );
}
