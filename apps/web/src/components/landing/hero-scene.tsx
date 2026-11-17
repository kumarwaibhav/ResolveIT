"use client";

import { useReducedMotion } from "@/lib/use-reduced-motion";
import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { MonolithMark } from "@/components/brand/monolith";
import { cn } from "@/lib/utils";

/**
 * The Monolith in 3D. Scattered signals (uncertain inputs) drift in from the left along two
 * engraved channels, converge at the calibration node, and leave as one ordered crimson stream.
 * three.js is imported lazily so it never weighs on the rest of the app.
 */
export function HeroScene({ className }: { className?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const [failed, setFailed] = useState(false);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);
  const syncRef = useRef<() => void>(() => {});

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    if (reduce) {
      setFailed(true);
      return;
    }
    let disposed = false;
    const cleanups: (() => void)[] = [];
    const cleanup = () => {
      while (cleanups.length) {
        try {
          cleanups.pop()!();
        } catch {
          /* keep releasing the rest */
        }
      }
    };

    void (async () => {
      const THREE = await import("three");
      if (disposed) return;
      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: !window.matchMedia("(pointer: coarse)").matches, alpha: true });
      } catch {
        setFailed(true);
        return;
      }
      cleanups.push(() => {
        renderer.dispose();
        renderer.forceContextLoss();
        renderer.domElement.remove();
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, window.matchMedia("(pointer: coarse)").matches ? 1.5 : 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.domElement.setAttribute("aria-hidden", "true");
      el.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      cleanups.push(() =>
        scene.traverse((o) => {
          const m = o as { geometry?: { dispose(): void }; material?: { dispose(): void } };
          m.geometry?.dispose();
          m.material?.dispose();
        }),
      );
      const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
      camera.position.set(3.6, 2.2, 12.5);
      camera.lookAt(0.3, -0.1, 0);

      const rig = new THREE.Group();
      scene.add(rig);

      // Tile: a continuous-corner square, extruded into a slab.
      const S = 4.2;
      const R = 0.85;
      const h = S / 2;
      const shape = new THREE.Shape();
      shape.moveTo(-h + R, -h);
      shape.lineTo(h - R, -h);
      shape.quadraticCurveTo(h, -h, h, -h + R);
      shape.lineTo(h, h - R);
      shape.quadraticCurveTo(h, h, h - R, h);
      shape.lineTo(-h + R, h);
      shape.quadraticCurveTo(-h, h, -h, h - R);
      shape.lineTo(-h, -h + R);
      shape.quadraticCurveTo(-h, -h, -h + R, -h);
      const tileGeo = new THREE.ExtrudeGeometry(shape, { depth: 0.7, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.08, bevelSegments: 6, curveSegments: 24 });
      tileGeo.translate(0, 0, -0.35);
      const tileMat = new THREE.MeshPhysicalMaterial({ color: 0x111114, roughness: 0.32, metalness: 0.55, clearcoat: 1, clearcoatRoughness: 0.25 });
      const tile = new THREE.Mesh(tileGeo, tileMat);
      rig.add(tile);

      const front = 0.45;
      const node = new THREE.Vector3(-0.35, 0, front);
      const y1 = 1.15;
      const lanes = [y1, -y1].map(
        (y) => new THREE.CubicBezierCurve3(new THREE.Vector3(-3.6, y, front), new THREE.Vector3(-1.6, y, front), new THREE.Vector3(-1.6, 0, front), node.clone()),
      );

      // Engraved input channels: quiet, translucent, uncertain.
      const channelMat = new THREE.MeshStandardMaterial({ color: 0xfaf8f5, emissive: 0xfaf8f5, emissiveIntensity: 0.18, transparent: true, opacity: 0.5, roughness: 0.6 });
      lanes.forEach((c) => rig.add(new THREE.Mesh(new THREE.TubeGeometry(c, 64, 0.075, 12, false), channelMat)));

      // Calibration node, breathing ring and the one crimson exit.
      const crimson = new THREE.Color(0xff3b30);
      const nodeMat = new THREE.MeshStandardMaterial({ color: crimson, emissive: crimson, emissiveIntensity: 1.6, roughness: 0.3 });
      const nodeMesh = new THREE.Mesh(new THREE.SphereGeometry(0.3, 32, 32), nodeMat);
      nodeMesh.position.copy(node);
      rig.add(nodeMesh);
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.52, 0.025, 12, 64), new THREE.MeshBasicMaterial({ color: crimson, transparent: true, opacity: 0.55 }));
      ring.position.copy(node);
      rig.add(ring);
      const railLen = 3.3;
      const rail = new THREE.Mesh(new THREE.BoxGeometry(railLen, 0.24, 0.12), nodeMat);
      rail.position.set(node.x + railLen / 2, 0, front);
      rig.add(rail);
      const glow = new THREE.PointLight(crimson, 6, 6, 1.6);
      glow.position.set(node.x + 0.4, 0, front + 0.8);
      rig.add(glow);

      scene.add(new THREE.AmbientLight(0xffffff, 0.55));
      const key = new THREE.DirectionalLight(0xffffff, 1.6);
      key.position.set(-4, 6, 8);
      scene.add(key);
      const rim = new THREE.DirectionalLight(0xff5a4f, 1.2);
      rim.position.set(6, -2, -6);
      scene.add(rim);

      // Signals. Before the node: scattered, pale. After: single file, crimson.
      const N = 220;
      const phase = new Float32Array(N);
      const lane = new Uint8Array(N);
      const jitter = new Float32Array(N * 2);
      const speed = new Float32Array(N);
      for (let i = 0; i < N; i++) {
        phase[i] = Math.random();
        lane[i] = i % 2;
        jitter[i * 2] = (Math.random() - 0.5) * 1.6;
        jitter[i * 2 + 1] = (Math.random() - 0.5) * 1.2;
        speed[i] = 0.05 + Math.random() * 0.05;
      }
      const pos = new Float32Array(N * 3);
      const col = new Float32Array(N * 3);
      const pGeo = new THREE.BufferGeometry();
      pGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      pGeo.setAttribute("color", new THREE.BufferAttribute(col, 3));
      const dot = document.createElement("canvas");
      dot.width = dot.height = 64;
      const g = dot.getContext("2d");
      if (!g) throw new Error("2D canvas unavailable");
      const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
      grad.addColorStop(0, "rgba(255,255,255,1)");
      grad.addColorStop(0.4, "rgba(255,255,255,0.6)");
      grad.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grad;
      g.fillRect(0, 0, 64, 64);
      const dotTex = new THREE.CanvasTexture(dot);
      cleanups.push(() => dotTex.dispose());
      const pMat = new THREE.PointsMaterial({ size: 0.16, map: dotTex, vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
      rig.add(new THREE.Points(pGeo, pMat));
      const pale = new THREE.Color(0xd8d4ce);
      const tmp = new THREE.Vector3();
      const tmpColor = new THREE.Color();
      const hot = [crimson.r * 1.4, crimson.g * 1.4, crimson.b * 1.4] as const;
      const place = () => {
        for (let i = 0; i < N; i++) {
          const t = phase[i]!;
          if (t < 0.6) {
            const u = t / 0.6;
            lanes[lane[i]!]!.getPoint(u, tmp);
            const spread = (1 - u) ** 1.5;
            tmp.y += jitter[i * 2]! * spread;
            tmp.z += 0.25 + jitter[i * 2 + 1]! * spread;
            tmp.x -= spread * 1.4;
            pos[i * 3] = tmp.x;
            pos[i * 3 + 1] = tmp.y;
            pos[i * 3 + 2] = tmp.z;
            tmpColor.copy(pale).lerp(crimson, u ** 6);
            col[i * 3] = tmpColor.r * 0.9;
            col[i * 3 + 1] = tmpColor.g * 0.9;
            col[i * 3 + 2] = tmpColor.b * 0.9;
          } else {
            const u = (t - 0.6) / 0.4;
            pos[i * 3] = node.x + u * (railLen + 0.8);
            pos[i * 3 + 1] = 0;
            pos[i * 3 + 2] = front + 0.12;
            col[i * 3] = hot[0];
            col[i * 3 + 1] = hot[1];
            col[i * 3 + 2] = hot[2];
          }
        }
        pGeo.attributes.position!.needsUpdate = true;
        pGeo.attributes.color!.needsUpdate = true;
      };
      place();

      // Ground: a fading blueprint grid.
      const grid = new THREE.GridHelper(30, 30, 0x888888, 0x888888);
      const gm = grid.material as InstanceType<typeof THREE.LineBasicMaterial>;
      gm.transparent = true;
      const syncGrid = () => (gm.opacity = document.documentElement.classList.contains("dark") ? 0.08 : 0.12);
      syncGrid();
      const themeWatch = new MutationObserver(syncGrid);
      themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
      cleanups.push(() => themeWatch.disconnect());
      grid.position.y = -2.9;
      scene.add(grid);

      rig.rotation.set(0.04, -0.2, 0);
      const target = { x: 0, y: 0 };
      const onMove = (e: PointerEvent) => {
        target.x = (e.clientX / window.innerWidth - 0.5) * 0.35;
        target.y = (e.clientY / window.innerHeight - 0.5) * 0.18;
      };
      window.addEventListener("pointermove", onMove, { passive: true });
      cleanups.push(() => window.removeEventListener("pointermove", onMove));

      const resize = () => {
        const w = el.clientWidth || 1;
        const hh = el.clientHeight || 1;
        renderer.setSize(w, hh, false);
        camera.aspect = w / hh;
        camera.position.z = w < 560 ? 16.5 : 12.5;
        camera.updateProjectionMatrix();
        renderer.render(scene, camera);
      };
      const ro = new ResizeObserver(resize);
      ro.observe(el);
      cleanups.push(() => ro.disconnect());
      resize();

      let raf = 0;
      let last = 0;
      const loop = (now: number) => {
        raf = requestAnimationFrame(loop);
        const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
        last = now;
        for (let i = 0; i < N; i++) phase[i] = (phase[i]! + speed[i]! * dt) % 1;
        place();
        const s = 1 + Math.sin(now / 700) * 0.08;
        ring.scale.set(s, s, s);
        rig.position.y = Math.sin(now / 1600) * 0.08;
        rig.rotation.y += (-0.2 + target.x - rig.rotation.y) * 0.04;
        rig.rotation.x += (0.04 + target.y - rig.rotation.x) * 0.04;
        renderer.render(scene, camera);
      };
      let onScreen = true;
      const sync = () => {
        const run = onScreen && !document.hidden && !pausedRef.current;
        if (run && !raf) {
          last = 0;
          raf = requestAnimationFrame(loop);
        } else if (!run && raf) {
          cancelAnimationFrame(raf);
          raf = 0;
        }
      };
      const io = new IntersectionObserver(([entry]) => {
        onScreen = entry?.isIntersecting ?? true;
        sync();
      });
      io.observe(el);
      document.addEventListener("visibilitychange", sync);
      syncRef.current = sync;
      cleanups.push(() => {
        cancelAnimationFrame(raf);
        io.disconnect();
        document.removeEventListener("visibilitychange", sync);
      });
      if (disposed) cleanup();
      else sync();
    })().catch(() => {
      cleanup();
      if (!disposed) setFailed(true);
    });

    return () => {
      disposed = true;
      cleanup();
    };
  }, [reduce]);

  const toggle = () => {
    pausedRef.current = !pausedRef.current;
    setPaused(pausedRef.current);
    syncRef.current();
  };

  return (
    <div className={cn("relative", className)}>
      <div ref={host} className="absolute inset-0 [&>canvas]:absolute [&>canvas]:inset-0 [&>canvas]:size-full" aria-hidden="true">
        {failed ? (
          <div className="grid size-full place-items-center">
            <MonolithMark size={220} />
          </div>
        ) : null}
      </div>
      {!failed && !reduce ? (
        <button
          type="button"
          onClick={toggle}
          aria-pressed={paused}
          className="glass absolute bottom-3 right-3 inline-flex min-h-10 items-center gap-1.5 rounded-full px-3 text-xs font-semibold text-muted-foreground hover:text-foreground"
        >
          {paused ? <Play aria-hidden="true" className="size-3.5" /> : <Pause aria-hidden="true" className="size-3.5" />}
          {paused ? "Play animation" : "Pause animation"}
        </button>
      ) : null}
    </div>
  );
}
