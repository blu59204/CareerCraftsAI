"use client";

import { MoonIcon, SunIcon } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/components/theme/ThemeProvider";

const ThemeSwitch = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => {
  const { theme, setTheme } = useTheme();
  const [checked, setChecked] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  useEffect(() => setChecked(theme === "dark"), [theme]);

  const handleCheckedChange = useCallback(
    (isChecked: boolean) => {
      setChecked(isChecked);
      setTheme(isChecked ? "dark" : "light");
    },
    [setTheme],
  );

  if (!mounted) return null;

  return (
    <div
      className={cn(
        "relative flex h-9 w-20 items-center justify-center",
        className,
      )}
      {...props}
    >
      <Switch
        checked={checked}
        onCheckedChange={handleCheckedChange}
        className={cn(
          "peer absolute inset-0 h-full w-full rounded-full border border-white/60 bg-white/[0.07] shadow-[inset_0_1px_0_rgba(255,255,255,0.55),0_8px_24px_rgba(0,0,0,0.10)] backdrop-blur-[24px] backdrop-saturate-[190%] transition-colors dark:border-white/15 dark:bg-black/[0.12]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          "[&>span]:z-10 [&>span]:h-7 [&>span]:w-7 [&>span]:rounded-full [&>span]:bg-background [&>span]:shadow",
          "data-[state=unchecked]:[&>span]:translate-x-1",
          "data-[state=checked]:[&>span]:translate-x-[44px]",
        )}
      />

      <span
        className={cn(
          "pointer-events-none absolute inset-y-0 left-2 z-0 flex items-center justify-center",
        )}
      >
        <SunIcon
          size={16}
          className={cn(
            "transition-all duration-200 ease-out",
            checked ? "text-muted-foreground/70" : "scale-110 text-foreground",
          )}
        />
      </span>

      <span
        className={cn(
          "pointer-events-none absolute inset-y-0 right-2 z-0 flex items-center justify-center",
        )}
      >
        <MoonIcon
          size={16}
          className={cn(
            "transition-all duration-200 ease-out",
            checked ? "scale-110 text-foreground dark:text-[#E1E0CC]" : "text-muted-foreground/70",
          )}
        />
      </span>
    </div>
  );
};

export default ThemeSwitch;
