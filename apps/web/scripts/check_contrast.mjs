// Fails if any text/surface pair in globals.css is below WCAG AA (4.5:1). Run: node scripts/check_contrast.mjs
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");
const [light, dark] = css.split("@media (prefers-color-scheme: dark) {\n    :root");
const tokens = (block) =>
  Object.fromEntries([...block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6});/g)].map((m) => [m[1], m[2]]));
const lum = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
const pairs = [
  ["foreground", "background"], ["foreground", "card"], ["muted-foreground", "background"],
  ["muted-foreground", "card"], ["muted-foreground", "muted"], ["primary-foreground", "primary"],
  ["primary", "card"], ["primary", "background"], ["accent-foreground", "accent"],
  ["ok", "ok-surface"], ["warn", "warn-surface"], ["risk", "risk-surface"], ["info", "info-surface"],
  ["destructive", "card"],
];
let failed = false;
for (const [name, block] of [["light", light], ["dark", dark]]) {
  const t = tokens(block);
  for (const [fg, bg] of pairs) {
    const r = ratio(t[fg], t[bg]);
    const ok = r >= 4.5;
    failed ||= !ok;
    console.log(`${ok ? "ok  " : "FAIL"} ${name.padEnd(5)} ${fg} on ${bg}: ${r.toFixed(2)}:1`);
  }
}
process.exit(failed ? 1 : 0);
