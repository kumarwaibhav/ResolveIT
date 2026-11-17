"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "@/lib/use-reduced-motion";
import { cn } from "@/lib/utils";

/**
 * A slow river of tickets. Each dot is a report drifting left to right; the ring is ResolveIT
 * reading the ones passing through it. Dots it would hand to a person turn crimson.
 * Plain 2D canvas: no WebGL, paused off-screen and in hidden tabs, static under reduced motion.
 */
interface Dot {
  u: number; // position along the river, 0..1
  v: number; // offset across the river, roughly -1..1
  z: number; // depth, 0 (far) .. 1 (near)
  p: number; // wobble phase
  flag: boolean; // would go to a person
}

const SPEED = 0.0065; // river widths per second: one crossing takes about two and a half minutes
const WAVE = 0.035; // how fast the river itself sways

function gauss() {
  let u = 0;
  let v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

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
    if (!el || !box) return;
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
    let t = 0;

    const readColors = () => {
      const cs = getComputedStyle(box);
      const fg = cs.getPropertyValue("--foreground").trim() || "#0c0c0e";
      const hex = fg.replace("#", "");
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
      const n = Math.round(Math.min(4800, Math.max(1400, W * (coarse ? 2 : 3.2))));
      if (dots.length !== n) {
        dots = Array.from({ length: n }, () => ({
          u: Math.random(),
          v: Math.max(-2.6, Math.min(2.6, gauss())) / 2.6,
          z: Math.random() ** 1.6,
          p: Math.random() * Math.PI * 2,
          flag: Math.random() < 0.035,
        }));
      }
    };

    // The river: low on the left, rising to the right, swaying slowly.
    const centre = (x: number) => H * (0.66 - 0.36 * (x / W)) + H * 0.07 * Math.sin((x / W) * Math.PI * 2.1 + t * WAVE * 6);
    const thick = (x: number) => H * (0.07 + 0.15 * Math.sin(Math.PI * Math.min(1, Math.max(0, x / W)) * 0.95 + 0.15));

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      const lensX = W * (0.6 + 0.05 * Math.sin(t * 0.045));
      const lensY = centre(lensX);
      const R = Math.max(64, Math.min(104, Math.min(W, H) * 0.14));
      let flagged = 0;

      for (const d of dots) {
        const u = (((d.u + t * SPEED * (0.55 + 0.45 * d.z)) % 1.1) + 1.1) % 1.1 - 0.05;
        const x = u * W;
        const y = centre(x) + d.v * thick(x) + Math.sin(t * 0.35 + d.p) * (2 + 3 * d.z);
        const edge = Math.min(1, Math.max(0, Math.min(u + 0.05, 1.05 - u) * 8));
        const dx = x - lensX;
        const dy = y - lensY;
        const inLens = dx * dx + dy * dy < R * R;
        const a = (0.16 + 0.62 * d.z) * (1 - 0.5 * Math.abs(d.v)) * edge;
        if (inLens && d.flag) {
          flagged++;
          ctx.fillStyle = signal;
          ctx.fillRect(x - 1.6, y - 1.6, 3.2, 3.2);
          continue;
        }
        const s = 0.7 + d.z * 1.5;
        ctx.fillStyle = `rgb(${ink} / ${Math.min(0.9, inLens ? a * 1.7 + 0.08 : a)})`;
        ctx.fillRect(x - s / 2, y - s / 2, s, s);
      }

      ctx.beginPath();
      ctx.arc(lensX, lensY, R, 0, Math.PI * 2);
      ctx.strokeStyle = `rgb(${ink} / 0.28)`;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.font = `12px ${mono}`;
      ctx.fillStyle = signal;
      const label = `${flagged} to a person`;
      const tw = ctx.measureText(label).width;
      const lx = lensX + R + 12 + tw < W - 8 ? lensX + R + 12 : lensX - R - 12 - tw;
      ctx.fillText(label, lx, lensY + 4);
    };

    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (!pausedRef.current) {
        t += dt;
        draw();
      }
      if (visible && !reduce) raf = requestAnimationFrame(loop);
    };
    const start = () => {
      cancelAnimationFrame(raf);
      last = performance.now();
      raf = requestAnimationFrame(loop);
    };

    readColors();
    resize();
    t = 18; // start mid-flow so the first frame already looks alive
    draw();

    const ro = new ResizeObserver(() => {
      resize();
      draw();
    });
    ro.observe(box);
    const mo = new MutationObserver(() => {
      readColors();
      draw();
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
          className="pointer-events-auto absolute right-4 top-[5.25rem] inline-flex min-h-10 items-center gap-2 rounded-full border bg-card/70 px-3.5 text-xs font-medium text-muted-foreground backdrop-blur hover:text-foreground sm:right-8"
        >
          {paused ? <Play aria-hidden="true" className="size-3.5" /> : <Pause aria-hidden="true" className="size-3.5" />}
          {paused ? "Play animation" : "Pause animation"}
        </button>
      )}
    </div>
  );
}
