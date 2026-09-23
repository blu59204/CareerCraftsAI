"use client";

/* Lightweight "career constellation" stage — canvas 2D, no WebGL, no new deps.
 * Fixed behind all app content. fps-capped, DPR-aware, reduced-motion aware,
 * subtle pointer parallax. Re-seeds colours when the theme flips. */

import { useEffect, useRef } from "react";
import { useTheme } from "@/components/theme/ThemeProvider";

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  kind: "base" | "violet" | "cyan";
}

export function ConstellationBackground() {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const { theme } = useTheme();

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isLight = theme === "light";

    // rgb triples tuned so dots read on both backgrounds
    const baseDot = isLight ? "40 44 90" : "190 196 255";
    const violet = isLight ? "108 64 230" : "158 138 255";
    const cyan = isLight ? "20 130 175" : "120 222 246";
    const lineRGB = isLight ? "70 76 130" : "150 162 230";

    let w = 0;
    let h = 0;
    let dpr = 1;
    let nodes: Node[] = [];
    const ptr = { x: 0.5, y: 0.5, tx: 0.5, ty: 0.5 };

    const seed = () => {
      const target = Math.round(56 * Math.min(1, (w * h) / (1440 * 900)));
      const n = Math.max(20, target);
      nodes = Array.from({ length: n }, (_, i) => {
        const kind: Node["kind"] = i % 11 === 0 ? "violet" : i % 17 === 0 ? "cyan" : "base";
        return {
          x: Math.random() * w,
          y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.12,
          vy: (Math.random() - 0.5) * 0.12,
          r: kind === "base" ? Math.random() * 1.3 + 0.5 : Math.random() * 1.7 + 1.4,
          kind,
        };
      });
    };

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
    };

    const colorOf = (k: Node["kind"]) => (k === "violet" ? violet : k === "cyan" ? cyan : baseDot);

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      ptr.x += (ptr.tx - ptr.x) * 0.05;
      ptr.y += (ptr.ty - ptr.y) * 0.05;
      const px = (ptr.x - 0.5) * 26;
      const py = (ptr.y - 0.5) * 26;

      const link = 134;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < link * link) {
            const alpha = (1 - Math.sqrt(d2) / link) * (isLight ? 0.13 : 0.16);
            ctx.strokeStyle = `rgba(${lineRGB} / ${alpha})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(a.x + px, a.y + py);
            ctx.lineTo(b.x + px, b.y + py);
            ctx.stroke();
          }
        }
      }

      for (const nd of nodes) {
        const glow = nd.kind !== "base";
        ctx.beginPath();
        ctx.arc(nd.x + px, nd.y + py, nd.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${colorOf(nd.kind)} / ${glow ? 0.9 : isLight ? 0.5 : 0.65})`;
        if (glow) {
          ctx.shadowBlur = 10;
          ctx.shadowColor = `rgba(${colorOf(nd.kind)} / 0.8)`;
        }
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    };

    const step = () => {
      for (const nd of nodes) {
        nd.x += nd.vx;
        nd.y += nd.vy;
        if (nd.x < -20) nd.x = w + 20;
        if (nd.x > w + 20) nd.x = -20;
        if (nd.y < -20) nd.y = h + 20;
        if (nd.y > h + 20) nd.y = -20;
      }
    };

    resize();

    let raf = 0;
    if (reduce) {
      draw();
    } else {
      const frameMs = 1000 / 36;
      let last = 0;
      const loop = (t: number) => {
        raf = requestAnimationFrame(loop);
        if (t - last < frameMs) return;
        last = t;
        step();
        draw();
      };
      raf = requestAnimationFrame(loop);
    }

    const onMove = (e: PointerEvent) => {
      ptr.tx = e.clientX / w;
      ptr.ty = e.clientY / h;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("resize", resize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("resize", resize);
    };
  }, [theme]);

  return (
    <div aria-hidden className="constellation-stage">
      <canvas ref={ref} className="constellation-canvas" />
    </div>
  );
}
