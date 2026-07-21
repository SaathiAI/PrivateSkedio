import { useEffect, useRef } from "react";
import type { AnimationTimeline } from "./useAnimationTimeline";

function smoothstep(start: number, end: number, value: number) {
  const t = Math.min(1, Math.max(0, (value - start) / (end - start)));
  return t * t * (3 - 2 * t);
}

export function HeroContent({ timeline }: { timeline: AnimationTimeline }) {
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => timeline.subscribe(({ progress, reducedMotion }) => {
    if (!contentRef.current) return;
    const fadeOut = 1 - smoothstep(1.8 / 7, 2.7 / 7, progress);
    const fadeIn = smoothstep(4.85 / 7, 5.55 / 7, progress);
    const opacity = reducedMotion ? 1 : progress < 2.7 / 7 ? fadeOut : fadeIn;
    contentRef.current.style.opacity = opacity.toFixed(3);
    contentRef.current.style.filter = `blur(${((1 - opacity) * 5).toFixed(2)}px)`;
    contentRef.current.style.transform = `translate3d(-50%, ${((1 - opacity) * -8).toFixed(2)}px, 0)`;
    contentRef.current.style.pointerEvents = opacity > 0.75 ? "auto" : "none";
  }), [timeline]);

  return (
    <div className="hero-content" ref={contentRef}>
      <p className="hero-context">Infrastructure for intelligent systems</p>
      <h1>Handle everything that happens after you deploy</h1>
      <p className="hero-copy">
        Build, observe, and operate intelligent systems through one unified infrastructure layer.
      </p>
      <a className="hero-cta" href="mailto:hello@skedio.ai?subject=SkedioAI%20demo">
        Book a demo <span aria-hidden="true">↗</span>
      </a>
    </div>
  );
}
