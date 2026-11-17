"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: "Light appearance", Icon: Sun },
  { value: "dark", label: "Dark appearance", Icon: Moon },
  { value: "system", label: "Match system appearance", Icon: Monitor },
] as const;

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return (
    <div role="group" aria-label="Appearance" className={cn("inline-flex rounded-full border bg-card/60 p-0.5", className)}>
      {OPTIONS.map(({ value, label, Icon }) => {
        const on = mounted && theme === value;
        return (
          <button
            key={value}
            type="button"
            aria-label={label}
            aria-pressed={on}
            onClick={() => setTheme(value)}
            className={cn(
              "grid size-8 place-items-center rounded-full text-muted-foreground transition-colors hover:text-foreground",
              on && "bg-foreground text-background hover:text-background",
            )}
          >
            <Icon aria-hidden="true" className="size-3.5" />
          </button>
        );
      })}
    </div>
  );
}
