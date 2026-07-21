import { useMemo, useState } from "react";
import { ParticleCanvas } from "./ParticleCanvas";
import { HeroContent } from "./HeroContent";
import { DebugPanel } from "./DebugPanel";
import { useAnimationTimeline } from "./useAnimationTimeline";
import "./hero.css";

function defaultParticleCount() {
  if (typeof window === "undefined") return 24_000;
  const cores = navigator.hardwareConcurrency || 4;
  if (window.innerWidth < 640) return cores <= 4 ? 12_000 : 18_000;
  if (window.innerWidth < 1024) return cores <= 4 ? 18_000 : 28_000;
  return cores >= 8 ? 48_000 : 34_000;
}

export function Hero() {
  const timeline = useAnimationTimeline();
  const initialCount = useMemo(defaultParticleCount, []);
  const [particleCount, setParticleCount] = useState(initialCount);
  const [pointSize, setPointSize] = useState(2.05);
  const [bloom, setBloom] = useState(0.32);

  return (
    <main className="hero" aria-label="SkedioAI intelligent infrastructure">
      <div className="hero-atmosphere" aria-hidden="true" />
      <ParticleCanvas timeline={timeline} particleCount={particleCount} pointSize={pointSize} bloom={bloom} />
      <div className="hero-hud" aria-hidden="true">
        <span className="hud-cross hud-cross-a">+</span>
        <span className="hud-cross hud-cross-b">+</span>
        <span className="hud-square hud-square-a" />
        <span className="hud-square hud-square-b" />
        <span className="hud-fragment hud-fragment-a" />
        <span className="hud-fragment hud-fragment-b" />
      </div>
      <header className="hero-nav">
        <a className="hero-brand" href="/" aria-label="SkedioAI home">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          SkedioAI
        </a>
        <nav aria-label="Primary navigation">
          <a href="#platform">Platform</a>
          <a href="#company">Company</a>
          <a href="mailto:hello@skedio.ai">Contact</a>
        </nav>
        <a className="nav-action" href="mailto:hello@skedio.ai?subject=SkedioAI%20demo">Talk to us <span aria-hidden="true">↗</span></a>
      </header>
      <HeroContent timeline={timeline} />
      <p className="hero-scroll-note">One system. From deployment to daily operation.</p>
      <DebugPanel
        timeline={timeline}
        particleCount={particleCount}
        pointSize={pointSize}
        bloom={bloom}
        onParticleCount={setParticleCount}
        onPointSize={setPointSize}
        onBloom={setBloom}
      />
    </main>
  );
}
