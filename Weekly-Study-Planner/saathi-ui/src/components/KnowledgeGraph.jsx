import { useEffect, useRef, useState, useCallback } from "react";
import { statsApi } from "../lib/statsApi.js";

// ─── Physics Engine ───────────────────────────────────────────────
class ForceGraph {
  constructor(nodes, links) {
    this.nodes = nodes.map(n => ({
      ...n,
      x: (Math.random() - 0.5) * 600,
      y: (Math.random() - 0.5) * 600,
      vx: 0,
      vy: 0,
    }));
    this.links = links;
    this.alpha = 1.0;
    this.alphaDecay = 0.012;
    this.velocityDecay = 0.6;
  }

  tick() {
    if (this.alpha < 0.001) return;
    this.alpha *= (1 - this.alphaDecay);

    const nodeMap = {};
    this.nodes.forEach(n => (nodeMap[n.id] = n));

    // Repulsion between all nodes
    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const a = this.nodes[i], b = this.nodes[j];
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const repulse = getRepulse(a) * getRepulse(b) / (dist * dist);
        const fx = (dx / dist) * repulse, fy = (dy / dist) * repulse;
        a.vx -= fx; a.vy -= fy;
        b.vx += fx; b.vy += fy;
      }
    }

    // Attraction along links
    this.links.forEach(link => {
      const a = nodeMap[link.source], b = nodeMap[link.target];
      if (!a || !b) return;
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const idealDist = 80 + getRadius(a) + getRadius(b);
      const force = (dist - idealDist) * 0.04 * this.alpha;
      const fx = (dx / dist) * force, fy = (dy / dist) * force;
      a.vx += fx; a.vy += fy;
      b.vx -= fx; b.vy -= fy;
    });

    // Center gravity
    this.nodes.forEach(n => {
      n.vx -= n.x * 0.005 * this.alpha;
      n.vy -= n.y * 0.005 * this.alpha;
    });

    // Apply velocity
    this.nodes.forEach(n => {
      if (n.fixed) { n.vx = 0; n.vy = 0; return; }
      n.vx *= this.velocityDecay;
      n.vy *= this.velocityDecay;
      n.x += n.vx;
      n.y += n.vy;
    });
  }

  heat() { this.alpha = 0.5; }
}

function getRadius(node) {
  if (node.group === "user")    return 28;
  if (node.group === "subject") return 22;
  if (node.group === "chapter") return 14;
  return 8;
}

function getRepulse(node) {
  if (node.group === "user")    return 700;
  if (node.group === "subject") return 380;
  if (node.group === "chapter") return 220;
  return 100;
}

// ─── Color Palette ────────────────────────────────────────────────
// Subject palette: vivid, saturated, clearly distinct from each other.
// Greens are reserved for "done" state.
const SUBJECT_COLORS = [
  { base: "#818cf8", glow: "rgba(129,140,248,0.45)" }, // indigo
  { base: "#f472b6", glow: "rgba(244,114,182,0.45)" }, // rose/pink
  { base: "#fb923c", glow: "rgba(251,146,60,0.45)"  }, // orange
  { base: "#38bdf8", glow: "rgba(56,189,248,0.45)"  }, // sky blue
  { base: "#e879f9", glow: "rgba(232,121,249,0.45)" }, // fuchsia
  { base: "#facc15", glow: "rgba(250,204,21,0.45)"  }, // yellow
  { base: "#a78bfa", glow: "rgba(167,139,250,0.45)" }, // violet
  { base: "#f87171", glow: "rgba(248,113,113,0.45)" }, // red
];

// Fixed colors for node groups (NOT subject-dependent)
const CHAPTER_COLOR  = { base: "#fbbf24", glow: "rgba(251,191,36,0.5)"  }; // amber gold
const PENDING_COLOR  = { base: "#94a3b8", glow: "rgba(148,163,184,0.4)" }; // bright slate (visible!)
const DONE_COLOR     = { base: "#22c55e", glow: "rgba(34,197,94,0.55)"  }; // bright emerald

const subjectColorMap = {};
let colorIndex = 0;

const normalizeGraphData = (data = {}) => {
  const nodes = (Array.isArray(data.nodes) ? data.nodes : []).map((node, index) => {
    const id = String(node.id ?? node.key ?? node.match_key ?? `node-${index}`);
    return {
      ...node,
      id,
      name: String(node.name ?? node.label ?? node.title ?? node.subject ?? id),
      group: node.group || node.type || "subtopic",
      status: node.status || "pending",
    };
  });
  const nodeIds = new Set(nodes.map(node => node.id));
  const links = (Array.isArray(data.links) ? data.links : [])
    .map(link => ({
      ...link,
      source: String(link.source?.id ?? link.source ?? ""),
      target: String(link.target?.id ?? link.target ?? ""),
    }))
    .filter(link => nodeIds.has(link.source) && nodeIds.has(link.target));

  return { nodes, links };
};

function getSubjectAccent(subjectName) {
  if (!subjectColorMap[subjectName]) {
    subjectColorMap[subjectName] = SUBJECT_COLORS[colorIndex % SUBJECT_COLORS.length];
    colorIndex++;
  }
  return subjectColorMap[subjectName];
}

function getNodeColor(node) {
  if (node.group === "user")    return { base: "#f8fafc", glow: "rgba(248,250,252,0.4)" };
  if (node.group === "subject") return getSubjectAccent(node.name);
  if (node.group === "chapter") return CHAPTER_COLOR;
  // Subtopic: done vs pending
  if (node.group === "subtopic") return node.status === "done" ? DONE_COLOR : PENDING_COLOR;
  return PENDING_COLOR;
}

// Link color: always returns a raw hex base color (no alpha)
function getLinkColor(sourceNode) {
  if (!sourceNode) return "#ffffff";
  if (sourceNode.group === "user")    return "#f8fafc";
  if (sourceNode.group === "subject") return getSubjectAccent(sourceNode.name).base;
  if (sourceNode.group === "chapter") return CHAPTER_COLOR.base;
  return "#94a3b8";
}

// Helper: hex color + alpha (0-1) -> rgba string
function hexAlpha(hex, alpha) {
  const r = parseInt(hex.slice(1,3), 16);
  const g = parseInt(hex.slice(3,5), 16);
  const b = parseInt(hex.slice(5,7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

// ─── Particle System ──────────────────────────────────────────────
class Particle {
  constructor(linkIndex) {
    this.linkIndex = linkIndex;
    this.progress = Math.random();
    this.speed = 0.002 + Math.random() * 0.003;
  }
  tick() { this.progress = (this.progress + this.speed) % 1; }
}

// ─── Main Graph Component ─────────────────────────────────────────
export function KnowledgeGraphModal({ onClose }) {
  const canvasRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [hoveredNode, setHoveredNode] = useState(null);
  const graphRef = useRef(null);
  const particlesRef = useRef([]);
  const animRef = useRef(null);
  const transformRef = useRef({ x: 0, y: 0, scale: 1 });
  const draggingRef = useRef(null);
  const panRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const hoveredRef = useRef(null);
  const [nodeCount, setNodeCount] = useState({ nodes: 0, links: 0 });
  const [graphError, setGraphError] = useState("");

  // ── Load data ──────────────────────────────────────────────────
  useEffect(() => {
    statsApi.graph()
      .then(data => {
        // Reset color map on each load so it's consistent
        Object.keys(subjectColorMap).forEach(k => delete subjectColorMap[k]);
        colorIndex = 0;
        const { nodes, links } = normalizeGraphData(data);
        graphRef.current = new ForceGraph(nodes, links);
        particlesRef.current = links.flatMap((_, i) =>
          Array.from({ length: 3 }, () => new Particle(i))
        );
        setNodeCount({ nodes: nodes.length, links: links.length });
        setLoading(false);
      })
      .catch(error => {
        setGraphError(error.message || "Could not load knowledge graph");
        setLoading(false);
      });
  }, []);

  // ── Canvas draw loop ───────────────────────────────────────────
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const fg = graphRef.current;
    if (!canvas || !fg) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    const { x: tx, y: ty, scale } = transformRef.current;
    const nodeMap = {};
    fg.nodes.forEach(n => (nodeMap[n.id] = n));

    // Tick physics
    fg.tick();
    particlesRef.current.forEach(p => p.tick());

    // Clear with deep dark bg
    ctx.fillStyle = "#080810";
    ctx.fillRect(0, 0, W, H);

    // Draw star field
    ctx.save();
    ctx.globalAlpha = 0.15;
    for (let i = 0; i < 120; i++) {
      // Stable pseudo-random stars using index as seed
      const sx = ((i * 137.508 * 7) % W);
      const sy = ((i * 97.3 * 11) % H);
      const sr = (i % 3 === 0) ? 1.2 : 0.6;
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(sx, sy, sr, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    ctx.save();
    ctx.translate(tx + W / 2, ty + H / 2);
    ctx.scale(scale, scale);

    const hovered = hoveredRef.current;

    // ─ Draw links ─────────────────────────────────────
    fg.links.forEach((link) => {
      const a = nodeMap[link.source], b = nodeMap[link.target];
      if (!a || !b) return;
      const isHoveredLink = hovered && (hovered.id === link.source || hovered.id === link.target);
      const linkBase = getLinkColor(a);

      // Gradient line — uses hexAlpha helper so no invalid CSS string concatenation
      const grad = ctx.createLinearGradient(a.x, a.y, b.x, b.y);
      grad.addColorStop(0, hexAlpha(linkBase, isHoveredLink ? 0.65 : 0.18));
      grad.addColorStop(1, hexAlpha(linkBase, isHoveredLink ? 0.25 : 0.04));

      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = grad;
      ctx.lineWidth = isHoveredLink ? 1.8 : 0.8;
      ctx.stroke();
    });

    // ─ Draw link particles ─────────────────────────────
    particlesRef.current.forEach(p => {
      const link = fg.links[p.linkIndex];
      if (!link) return;
      const a = nodeMap[link.source], b = nodeMap[link.target];
      if (!a || !b) return;
      const hex = getLinkColor(a);
      const px = a.x + (b.x - a.x) * p.progress;
      const py = a.y + (b.y - a.y) * p.progress;
      ctx.beginPath();
      ctx.arc(px, py, 2, 0, Math.PI * 2);
      ctx.fillStyle = hexAlpha(hex, 0.75);
      ctx.fill();
    });

    // ─ Draw nodes ─────────────────────────────────────
    fg.nodes.forEach(node => {
      const r = getRadius(node);
      const color = getNodeColor(node);
      const isHov = hovered && hovered.id === node.id;
      const isConnected = hovered && fg.links.some(l => (l.source === hovered.id && l.target === node.id) || (l.target === hovered.id && l.source === node.id));
      const isDone = node.status === "done";
      const opacity = hovered && !isHov && !isConnected ? 0.25 : 1;

      ctx.globalAlpha = opacity;

      // Outer glow
      const showGlow = isHov || node.group === "user" || node.group === "subject" || isDone;
      if (showGlow) {
        const glowRadius = r + (node.group === "user" ? 18 : node.group === "subject" ? 14 : 12);
        const glowHex = isDone ? "#22c55e"
          : node.group === "user" ? "#f8fafc"
          : color.base;
        const grd = ctx.createRadialGradient(node.x, node.y, r * 0.4, node.x, node.y, glowRadius);
        grd.addColorStop(0, hexAlpha(glowHex, 0.35));
        grd.addColorStop(1, hexAlpha(glowHex, 0));
        ctx.beginPath();
        ctx.arc(node.x, node.y, glowRadius, 0, Math.PI * 2);
        ctx.fillStyle = grd;
        ctx.fill();
      }

      // Pulse ring for subject/user nodes
      if (node.group === "subject" || node.group === "user") {
        const pulse = r + 7 + Math.sin(Date.now() * 0.0025 + node.x) * 3;
        ctx.beginPath();
        ctx.arc(node.x, node.y, pulse, 0, Math.PI * 2);
        ctx.strokeStyle = color.base + (node.group === "user" ? "55" : "33");
        ctx.lineWidth = node.group === "user" ? 1.5 : 1;
        ctx.stroke();
      }

      // Draw circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);

      if (node.group === "user") {
        // Special: white glowing orb
        const radGrad = ctx.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 0, node.x, node.y, r);
        radGrad.addColorStop(0, "rgba(255,255,255,0.95)");
        radGrad.addColorStop(1, "rgba(255,255,255,0.5)");
        ctx.fillStyle = radGrad;
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,0.9)";
        ctx.lineWidth = 2;
        ctx.stroke();
      } else if (node.group === "subject") {
        const radGrad = ctx.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 0, node.x, node.y, r);
        radGrad.addColorStop(0, color.base + "cc");
        radGrad.addColorStop(1, color.base + "44");
        ctx.fillStyle = radGrad;
        ctx.fill();
        ctx.strokeStyle = color.base;
        ctx.lineWidth = 2;
        ctx.stroke();
      } else if (node.group === "chapter") {
        // Amber gold — solid and clearly visible
        const radGrad = ctx.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 0, node.x, node.y, r);
        radGrad.addColorStop(0, "#fde68a"); // bright amber center
        radGrad.addColorStop(1, "#f59e0b"); // deep amber edge
        ctx.fillStyle = radGrad;
        ctx.fill();
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = 2;
        ctx.stroke();
      } else {
        // Subtopic — bright slate if pending, vivid green if done
        if (isDone) {
          const radGrad = ctx.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 0, node.x, node.y, r);
          radGrad.addColorStop(0, "#4ade80"); // lime green center
          radGrad.addColorStop(1, "#16a34a"); // deep green edge
          ctx.fillStyle = radGrad;
          ctx.fill();
          ctx.strokeStyle = "#22c55e";
          ctx.lineWidth = 1.5;
          ctx.stroke();
        } else {
          const radGrad = ctx.createRadialGradient(node.x - r * 0.3, node.y - r * 0.3, 0, node.x, node.y, r);
          radGrad.addColorStop(0, "#cbd5e1"); // light slate center
          radGrad.addColorStop(1, "#475569"); // dark slate edge
          ctx.fillStyle = radGrad;
          ctx.fill();
          ctx.strokeStyle = "#94a3b8";
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      // Labels
      // Show label: always for user/subject, for chapter at any zoom, for subtopics when hovered/connected or zoomed
      const isLarge = node.group === "user" || node.group === "subject";
      const showLabel = isHov || isConnected || isLarge || node.group === "chapter" || scale > 1.5;
      if (showLabel) {
        const fontSize = node.group === "user" ? 14 : node.group === "subject" ? 13 : node.group === "chapter" ? 11 : 9;
        const weight = (node.group === "user" || node.group === "subject") ? "600" : "400";
        ctx.font = `${weight} ${fontSize}px 'DM Sans', sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        const label = node.name.length > 24 ? node.name.slice(0, 22) + "…" : node.name;
        const textY = node.y + r + (node.group === "user" ? 20 : node.group === "subject" ? 16 : 13);

        // Text shadow
        ctx.fillStyle = "rgba(0,0,0,0.9)";
        ctx.fillText(label, node.x + 0.5, textY + 0.5);

        ctx.fillStyle = isHov ? "#ffffff"
          : node.group === "user" ? "#ffffff"
          : node.group === "subject" ? color.base
          : node.group === "chapter" ? "#fde68a"
          : isDone ? "#4ade80"
          : "#e2e8f0"; // very light slate — readable on dark
        ctx.fillText(label, node.x, textY);
      }

      ctx.globalAlpha = 1;
    });

    ctx.restore();
  }, []);

  // ── Start / stop animation ─────────────────────────────────────
  useEffect(() => {
    if (!loading) {
      const safeTick = () => {
        try {
          draw();
          animRef.current = requestAnimationFrame(safeTick);
        } catch (error) {
          setGraphError(error.message || "Knowledge graph render failed");
          if (animRef.current) cancelAnimationFrame(animRef.current);
        }
      };
      animRef.current = requestAnimationFrame(safeTick);
    }
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [loading, draw]);

  // ── Resize canvas ──────────────────────────────────────────────
  useEffect(() => {
    const resize = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  // ── Pointer to world coords ────────────────────────────────────
  const toWorld = (clientX, clientY) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const { x, y, scale } = transformRef.current;
    const W = canvas.width, H = canvas.height;
    return {
      wx: (clientX - rect.left - W / 2 - x) / scale,
      wy: (clientY - rect.top  - H / 2 - y) / scale,
    };
  };

  const getNodeAt = (wx, wy) => {
    const fg = graphRef.current;
    if (!fg) return null;
    for (const n of fg.nodes) {
      const r = getRadius(n) + 6;
      if ((n.x - wx) ** 2 + (n.y - wy) ** 2 < r * r) return n;
    }
    return null;
  };

  // ── Mouse events ───────────────────────────────────────────────
  const onMouseDown = e => {
    const { wx, wy } = toWorld(e.clientX, e.clientY);
    const node = getNodeAt(wx, wy);
    if (node) {
      draggingRef.current = node;
      node.fixed = true;
      graphRef.current?.heat();
    } else {
      panRef.current = { startX: e.clientX, startY: e.clientY, tx: transformRef.current.x, ty: transformRef.current.y };
    }
  };

  const onMouseMove = e => {
    if (draggingRef.current) {
      const { wx, wy } = toWorld(e.clientX, e.clientY);
      draggingRef.current.x = wx;
      draggingRef.current.y = wy;
      draggingRef.current.vx = 0;
      draggingRef.current.vy = 0;
      return;
    }
    if (panRef.current) {
      transformRef.current.x = panRef.current.tx + (e.clientX - panRef.current.startX);
      transformRef.current.y = panRef.current.ty + (e.clientY - panRef.current.startY);
      return;
    }
    // Hover detection
    const { wx, wy } = toWorld(e.clientX, e.clientY);
    const node = getNodeAt(wx, wy);
    hoveredRef.current = node;
    setHoveredNode(node);
    if (node) {
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      setTooltip({ node, x: e.clientX - rect.left, y: e.clientY - rect.top });
    } else {
      setTooltip(null);
    }
  };

  const onMouseUp = () => {
    if (draggingRef.current) {
      draggingRef.current.fixed = false;
      draggingRef.current = null;
    }
    panRef.current = null;
  };

  const onWheel = e => {
    e.preventDefault();
    const delta = -e.deltaY * 0.001;
    transformRef.current.scale = Math.max(0.2, Math.min(5, transformRef.current.scale * (1 + delta)));
  };

  const onMouseLeave = () => {
    hoveredRef.current = null;
    setHoveredNode(null);
    setTooltip(null);
    if (draggingRef.current) { draggingRef.current.fixed = false; draggingRef.current = null; }
    panRef.current = null;
  };

  // ── Legend ─────────────────────────────────────────────────────
  const legend = [
    { label: "You",             color: "#f8fafc",  stroke: "#f8fafc",  r: 11 },
    { label: "Subject",         color: "#818cf877", stroke: "#818cf8",  r: 9  },
    { label: "Chapter",         color: "#fbbf2466", stroke: "#fbbf24",  r: 6  },
    { label: "Subtopic — todo", color: "#47556988", stroke: "#64748b",  r: 4  },
    { label: "Subtopic — done", color: "#22c55e88", stroke: "#22c55e",  r: 4  },
  ];

  return (
    <div style={{
      position: "fixed", inset: 0,
      background: "rgba(0,0,0,0.75)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 3000,
      animation: "fadeIn 0.3s ease",
      backdropFilter: "blur(20px)",
    }}>
      <div style={{ position: "absolute", inset: 0 }} onClick={onClose} />
      
      <div style={{
        position: "relative",
        width: "92vw", height: "92vh",
        borderRadius: 28,
        border: "1px solid rgba(255,255,255,0.08)",
        boxShadow: "0 50px 120px rgba(0,0,0,0.8), inset 0 1px 0 rgba(255,255,255,0.05)",
        overflow: "hidden",
        animation: "modalScaleUp 0.35s cubic-bezier(0.16,1,0.3,1) forwards",
        background: "#080810",
      }}>
        {/* Canvas */}
        <canvas
          ref={canvasRef}
          style={{ width: "100%", height: "100%", display: "block", cursor: hoveredNode ? "grab" : "default" }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseLeave}
          onWheel={onWheel}
        />

        {/* Header overlay */}
        <div style={{
          position: "absolute", top: 28, left: 32,
          pointerEvents: "none",
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.15em", textTransform: "uppercase", color: "rgba(255,255,255,0.3)", marginBottom: 6 }}>Knowledge Graph</div>
          <h2 style={{ margin: 0, fontSize: 30, fontFamily: "'Fraunces', serif", fontStyle: "italic", fontWeight: 400, color: "#fff", lineHeight: 1 }}>Your Brain</h2>
          <p style={{ margin: "8px 0 0", fontSize: 12, color: "rgba(255,255,255,0.35)" }}>
            {nodeCount.nodes} nodes · {nodeCount.links} connections · drag nodes · scroll to zoom
          </p>
        </div>

        {/* Close button */}
        <button onClick={onClose} style={{
          position: "absolute", top: 24, right: 24,
          background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: "50%", cursor: "pointer", color: "rgba(255,255,255,0.5)",
          width: 36, height: 36, display: "flex", alignItems: "center", justifyContent: "center",
          transition: "all 0.2s", fontSize: 16, zIndex: 10,
        }}
          onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.12)"; e.currentTarget.style.color = "#fff"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.color = "rgba(255,255,255,0.5)"; }}
        >✕</button>

        {/* Legend */}
        <div style={{
          position: "absolute", bottom: 28, left: 32,
          display: "flex", flexDirection: "column", gap: 8,
          pointerEvents: "none",
        }}>
          {legend.map(l => (
            <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <svg width={24} height={24}>
                <circle cx={12} cy={12} r={l.r} fill={l.color} stroke={l.stroke} strokeWidth={1.5} />
              </svg>
              <span style={{ fontSize: 12, color: "rgba(255,255,255,0.45)" }}>{l.label}</span>
            </div>
          ))}
        </div>

        {/* Zoom controls */}
        <div style={{
          position: "absolute", bottom: 28, right: 32,
          display: "flex", flexDirection: "column", gap: 6,
        }}>
          {[
            { label: "+", delta: 0.3 },
            { label: "−", delta: -0.3 },
          ].map(btn => (
            <button key={btn.label} onClick={() => {
              transformRef.current.scale = Math.max(0.2, Math.min(5, transformRef.current.scale * (1 + btn.delta)));
            }} style={{
              width: 36, height: 36, borderRadius: 10, background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.7)",
              cursor: "pointer", fontSize: 18, display: "flex", alignItems: "center",
              justifyContent: "center", transition: "all 0.2s",
            }}
              onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.12)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; }}
            >{btn.label}</button>
          ))}
          <button onClick={() => { transformRef.current = { x: 0, y: 0, scale: 1 }; }} style={{
            width: 36, height: 36, borderRadius: 10, background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.7)",
            cursor: "pointer", fontSize: 11, display: "flex", alignItems: "center",
            justifyContent: "center", transition: "all 0.2s",
          }}
            onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.12)"; }}
            onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; }}
          >⌂</button>
        </div>

        {/* Loading */}
        {loading && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", color: "rgba(255,255,255,0.5)", gap: 16,
          }}>
            <div style={{ width: 40, height: 40, borderRadius: "50%", border: "2px solid rgba(129,140,248,0.2)", borderTopColor: "#818cf8", animation: "spin 0.8s linear infinite" }} />
            <span style={{ fontSize: 14, fontFamily: "'Fraunces', serif", fontStyle: "italic" }}>Building your constellation…</span>
          </div>
        )}

        {graphError && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
            background: "rgba(8,8,16,0.82)", color: "rgba(255,255,255,0.75)", padding: 24,
          }}>
            <div style={{ maxWidth: 420, textAlign: "center", lineHeight: 1.6 }}>
              <div style={{ fontSize: 18, color: "#fff", marginBottom: 8 }}>Knowledge graph unavailable</div>
              <div style={{ fontSize: 13 }}>{graphError}</div>
            </div>
          </div>
        )}

        {/* Tooltip */}
        {tooltip && (
          <div style={{
            position: "absolute",
            left: tooltip.x + 16, top: tooltip.y - 12,
            background: "rgba(10,10,20,0.95)",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: 10, padding: "8px 14px",
            pointerEvents: "none",
            boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
            backdropFilter: "blur(10px)",
            maxWidth: 220,
            animation: "fadeIn 0.15s ease",
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", marginBottom: 4 }}>{tooltip.node.name}</div>
            <div style={{ fontSize: 11, color: "rgba(255,255,255,0.45)", textTransform: "capitalize", marginBottom: tooltip.node.subject ? 3 : 0 }}>
              {tooltip.node.group}{tooltip.node.status === "done" ? " · ✓ completed" : ""}
            </div>
            {tooltip.node.subject && tooltip.node.group !== "user" && tooltip.node.group !== "subject" && (
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>{tooltip.node.subject}</div>
            )}
            {tooltip.node.sessions > 0 && (
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginTop: 2 }}>{tooltip.node.sessions} session{tooltip.node.sessions !== 1 ? 's' : ''}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
