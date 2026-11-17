"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "@/lib/use-reduced-motion";
import { cn } from "@/lib/utils";

/**
 * A slow, wide river of tickets drifting left to right like floating bubbles.
 * The ring is ResolveIT reading: it follows the pointer, and tickets inside it that it
 * would hand to a person pop crimson. With no pointer it drifts along the river on its own.
 * Plain 2D canvas, paused off-screen and in hidden tabs, static under reduced motion.
 */
interface Dot {
  u: number; // position along the stream, 0..1.1
  s: number; // unused, kept for shape
  v: number; // offset inside the strand
  z: number; // depth, 0 far .. 1 near
  p: number; // phase
  k: number; // personal speed factor
  incident: boolean;
}

const SPEED = 0.0065; // stream widths per second: a crossing takes about two and a half minutes

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
    let t = 18;
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
      const n = Math.round(Math.min(2600, Math.max(900, W * (coarse ? 1.1 : 1.7))));
      if (dots.length !== n) {
        dots = Array.from({ length: n }, () => {
          const a = Math.random() + Math.random() + Math.random() + Math.random() - 2; // soft bell, -2..2
          return {
            u: Math.random() * 1.1,
            s: 0,
            v: a / 2,
            z: Math.random() ** 1.6,
            p: Math.random() * Math.PI * 2,
            k: 0.55 + 0.45 * Math.random(),
            incident: Math.random() < 0.05,
          };
        });
      }
    };

    // The river: low on the left, rising to the right, swaying slowly. Wide and soft, like the first version.
    const centre = (x: number) => H * (0.6 - 0.36 * (x / W)) + H * 0.07 * Math.sin((x / W) * Math.PI * 2.1 + t * 0.21);
    const thick = (x: number) => H * (0.05 + 0.13 * Math.sin(Math.PI * Math.min(1, Math.max(0, x / W)) * 0.95 + 0.15));

    const place = (d: Dot) => {
      const u = d.u + t * SPEED * d.k;
      const uu = (((u % 1.1) + 1.1) % 1.1) - 0.05;
      const x = uu * W;
      const y = centre(x) + d.v * thick(x) + Math.sin(t * 0.35 + d.p) * (2 + 3 * d.z);
      return { x, y, uu };
    };

    const draw = (dt: number) => {
      ctx.clearRect(0, 0, W, H);

      // Lens: follow the pointer when present, otherwise drift along the stream.
      if (!lens.steer) {
        lens.idle += dt;
        lens.tx = W * (0.6 + 0.12 * Math.sin(lens.idle * 0.12));
        lens.ty = centre(lens.tx);
      }
      const ease = 1 - Math.exp(-dt * (lens.steer ? 9 : 2));
      lens.x += (lens.tx - lens.x) * ease;
      lens.y += (lens.ty - lens.y) * ease;
      const R = Math.max(56, Math.min(96, Math.min(W, H) * 0.15));

      const hits: [number, number][] = [];
      for (const d of dots) {
        const { x, y, uu } = place(d);
        const edge = Math.min(1, Math.max(0, Math.min(uu + 0.05, 1.05 - uu) * 8));
        const dx = x - lens.x;
        const dy = y - lens.y;
        const inLens = dx * dx + dy * dy < R * R;
        if (inLens && d.incident) {
          hits.push([x, y]);
          continue;
        }
        const a = (0.12 + 0.56 * d.z) * (1 - 0.5 * Math.abs(d.v)) * edge;
        const s = 0.7 + d.z * 1.4;
        ctx.fillStyle = `rgb(${ink} / ${Math.min(0.9, inLens ? a * 1.6 + 0.08 : a)})`;
        ctx.fillRect(x - s / 2, y - s / 2, s, s);
      }

      // Tickets the lens would hand to a person simply pop crimson.
      ctx.fillStyle = signal;
      ctx.shadowColor = signal;
      ctx.shadowBlur = 8;
      for (const [x, y] of hits) {
        ctx.beginPath();
        ctx.arc(x, y, 2.2, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;

      ctx.beginPath();
      ctx.arc(lens.x, lens.y, R, 0, Math.PI * 2);
      ctx.strokeStyle = `rgb(${ink} / 0.35)`;
      ctx.stroke();
      ctx.font = `12px ${mono}`;
      ctx.fillStyle = signal;
      const label = `${hits.length} flagged for a person`;
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
    lens.y = lens.ty = centre(lens.x);
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
