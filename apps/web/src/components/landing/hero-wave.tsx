"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "@/lib/use-reduced-motion";
import { cn } from "@/lib/utils";

/**
 * A narrow, braided stream of tickets drifting left to right like floating bubbles.
 * The ring is ResolveIT reading: it follows the pointer, and any ticket inside it that
 * would be an incident turns crimson and gets a marker. With no pointer it drifts on its own.
 * Plain 2D canvas, paused off-screen and in hidden tabs, static under reduced motion.
 */
interface Dot {
  u: number; // position along the stream, 0..1.1
  s: number; // strand
  v: number; // offset inside the strand
  z: number; // depth, 0 far .. 1 near
  p: number; // phase
  k: number; // personal speed factor
  incident: boolean;
}

const STRANDS = [
  { amp: 0.32, k: 1.6, w: 0.21, off: 0 },
  { amp: 0.42, k: 2.3, w: -0.15, off: 1.7 },
  { amp: 0.26, k: 3.1, w: 0.27, off: 3.4 },
  { amp: 0.5, k: 1.1, w: 0.11, off: 5.0 },
];
const SPEED = 0.0075; // stream widths per second, before per-dot variation

export function HeroWave({ className }: { className?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const reduce = useReducedMotion();
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);
  pausedRef.current = paused;

  useEffect(() => {
    const el = canvas.current;
    const box = host.current;
    const zone = box?.parentElement;
    if (!el || !box || !zone) return;
    const ctx = el.getContext("2d");
    if (!ctx) return;

    let W = 0;
    let H = 0;
    let dots: Dot[] = [];
    let ink = "12 12 14";
    let signal = "#c8241a";
    let mono = "ui-monospace, monospace";
    let visible = true;
    let raf = 0;
    let last = performance.now();
    let t = 24;
    // Lens: where it is, where it is heading, and whether a pointer is steering it.
    const lens = { x: 0, y: 0, tx: 0, ty: 0, steer: false, idle: 0 };

    const readColors = () => {
      const cs = getComputedStyle(box);
      const hex = (cs.getPropertyValue("--foreground").trim() || "#0c0c0e").replace("#", "");
      if (hex.length === 6) ink = `${parseInt(hex.slice(0, 2), 16)} ${parseInt(hex.slice(2, 4), 16)} ${parseInt(hex.slice(4, 6), 16)}`;
      signal = cs.getPropertyValue("--signal").trim() || signal;
      mono = cs.getPropertyValue("--font-mono").trim() || mono;
    };

    const resize = () => {
      const r = box.getBoundingClientRect();
      W = r.width;
      H = r.height;
      const coarse = window.matchMedia("(pointer: coarse)").matches;
      const dpr = Math.min(window.devicePixelRatio || 1, coarse ? 1.5 : 2);
      el.width = Math.round(W * dpr);
      el.height = Math.round(H * dpr);
      el.style.width = `${W}px`;
      el.style.height = `${H}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.round(Math.min(3000, Math.max(1100, W * (coarse ? 1.6 : 2.1))));
      if (dots.length !== n) {
        dots = Array.from({ length: n }, () => {
          const a = Math.random() + Math.random() + Math.random() - 1.5; // soft bell, -1.5..1.5
          return {
            u: Math.random() * 1.1,
            s: Math.floor(Math.random() * STRANDS.length),
            v: a / 1.5,
            z: Math.random() ** 1.5,
            p: Math.random() * Math.PI * 2,
            k: 0.55 + Math.random() * 0.8,
            incident: Math.random() < 0.06,
          };
        });
      }
    };

    // Centre line of the whole stream: tapered at the left, lifting gently to the right, slowly breathing.
    const base = (x: number) => {
      const f = x / W;
      return H * (0.56 - 0.1 * f) + H * 0.2 * Math.sin(f * 5.4 + t * 0.16) + H * 0.07 * Math.sin(f * 12.5 - t * 0.12 + 1.3);
    };
    // Width of the stream: thin at both ends, widest a little right of centre. Narrow overall.
    const width = (x: number) => {
      const f = Math.min(1, Math.max(0, x / W));
      return H * (0.07 + 0.13 * (0.55 + 0.45 * Math.sin(f * 7 - t * 0.1)) * Math.sin(Math.PI * Math.min(1, f + 0.08)) ** 0.8);
    };

    const place = (d: Dot) => {
      // Non-uniform flow: speed swells and eases along the stream, so dots bunch and spread like bubbles.
      const u = d.u + t * SPEED * d.k * (1 + 0.35 * Math.sin(d.u * 9 + t * 0.2));
      const uu = (((u % 1.1) + 1.1) % 1.1) - 0.05;
      const x = uu * W;
      const st = STRANDS[d.s]!;
      const f = x / W;
      const strand = Math.sin(f * Math.PI * 2 * st.k + t * st.w + st.off) * st.amp;
      const w = width(x);
      const y = base(x) + (strand + d.v * 0.55) * w + Math.sin(t * 0.6 + d.p) * (1.5 + 2.5 * d.z);
      return { x, y, uu };
    };

    const draw = (dt: number) => {
      ctx.clearRect(0, 0, W, H);

      // Lens: follow the pointer when present, otherwise drift along the stream.
      if (!lens.steer) {
        lens.idle += dt;
        lens.tx = W * (0.6 + 0.12 * Math.sin(lens.idle * 0.12));
        lens.ty = base(lens.tx);
      }
      const ease = 1 - Math.exp(-dt * (lens.steer ? 9 : 2));
      lens.x += (lens.tx - lens.x) * ease;
      lens.y += (lens.ty - lens.y) * ease;
      const R = Math.max(50, Math.min(92, H * 0.27));

      const hits: [number, number][] = [];
      for (const d of dots) {
        const { x, y, uu } = place(d);
        const edge = Math.min(1, Math.max(0, Math.min(uu + 0.05, 1.05 - uu) * 7));
        const dx = x - lens.x;
        const dy = y - lens.y;
        const inLens = dx * dx + dy * dy < R * R;
        if (inLens && d.incident) {
          hits.push([x, y]);
          continue;
        }
        const a = (0.14 + 0.6 * d.z) * (1 - 0.35 * Math.abs(d.v)) * edge;
        const s = 0.7 + d.z * 1.3;
        ctx.fillStyle = `rgb(${ink} / ${Math.min(0.92, inLens ? a * 1.6 + 0.1 : a)})`;
        ctx.beginPath();
        ctx.arc(x, y, s / 2, 0, Math.PI * 2);
        ctx.fill();
      }

      // Incidents inside the lens: crimson, each with a small marker ring.
      ctx.fillStyle = signal;
      ctx.strokeStyle = signal;
      ctx.lineWidth = 1;
      for (const [x, y] of hits) {
        ctx.fillRect(x - 1.75, y - 1.75, 3.5, 3.5);
        ctx.globalAlpha = 0.55;
        ctx.strokeRect(x - 4.5, y - 4.5, 9, 9);
        ctx.globalAlpha = 1;
      }

      ctx.beginPath();
      ctx.arc(lens.x, lens.y, R, 0, Math.PI * 2);
      ctx.strokeStyle = `rgb(${ink} / 0.35)`;
      ctx.stroke();
      ctx.font = `12px ${mono}`;
      ctx.fillStyle = signal;
      const label = `${hits.length} ${hits.length === 1 ? "incident" : "incidents"} found`;
      const tw = ctx.measureText(label).width;
      const lx = lens.x + R + 12 + tw < W - 8 ? lens.x + R + 12 : lens.x - R - 12 - tw;
      ctx.fillText(label, lx, lens.y + 4);
    };

    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (!pausedRef.current) t += dt;
      draw(dt);
      if (visible && !reduce) raf = requestAnimationFrame(loop);
    };
    const start = () => {
      cancelAnimationFrame(raf);
      last = performance.now();
      raf = requestAnimationFrame(loop);
    };

    readColors();
    resize();
    lens.x = lens.tx = W * 0.6;
    lens.y = lens.ty = base(lens.x);
    draw(0);

    const onMove = (e: PointerEvent) => {
      const r = box.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      if (y < 0 || y > r.height) {
        lens.steer = false;
        return;
      }
      lens.steer = true;
      lens.tx = x;
      lens.ty = y;
      if (reduce) {
        lens.x = x;
        lens.y = y;
        draw(0);
      }
    };
    const onLeave = () => {
      lens.steer = false;
    };
    zone.addEventListener("pointermove", onMove);
    zone.addEventListener("pointerleave", onLeave);

    const ro = new ResizeObserver(() => {
      resize();
      draw(0);
    });
    ro.observe(box);
    const mo = new MutationObserver(() => {
      readColors();
      draw(0);
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    const io = new IntersectionObserver(([e]) => {
      visible = !!e?.isIntersecting && document.visibilityState === "visible";
      if (visible && !reduce) start();
      else cancelAnimationFrame(raf);
    });
    io.observe(box);
    const onVis = () => {
      visible = document.visibilityState === "visible";
      if (visible && !reduce) start();
      else cancelAnimationFrame(raf);
    };
    document.addEventListener("visibilitychange", onVis);
    if (!reduce) start();

    return () => {
      cancelAnimationFrame(raf);
      zone.removeEventListener("pointermove", onMove);
      zone.removeEventListener("pointerleave", onLeave);
      ro.disconnect();
      mo.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [reduce]);

  return (
    <div ref={host} className={cn("pointer-events-none", className)}>
      <canvas ref={canvas} aria-hidden="true" className="block" />
      {reduce ? null : (
        <button
          type="button"
          onClick={() => setPaused((p) => !p)}
          aria-pressed={paused}
          className="pointer-events-auto absolute right-4 top-[4.5rem] inline-flex min-h-10 items-center gap-2 rounded-full border bg-card/70 px-3.5 text-[13px] font-medium text-muted-foreground backdrop-blur hover:text-foreground sm:right-8"
        >
          {paused ? <Play aria-hidden="true" className="size-3.5" /> : <Pause aria-hidden="true" className="size-3.5" />}
          {paused ? "Play" : "Pause"}
          <span className="sr-only"> background animation</span>
        </button>
      )}
    </div>
  );
}
