"use client";

import { motion } from "motion/react";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { SPRING_SOFT } from "./motion";

/**
 * Segmented pill control with a spring-animated active indicator.
 * Use for in-page tabs and small option sets. Renders role="tablist" when
 * `asTabs` (default) — give each panel `id={`${id}-panel-${value}`}` if needed.
 */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
  size = "md",
  asTabs = true,
  ariaLabel,
  id,
}: {
  value: T;
  onChange: (next: T) => void;
  options: ReadonlyArray<{ value: T; label: ReactNode; icon?: ReactNode; count?: number }>;
  className?: string;
  size?: "sm" | "md";
  asTabs?: boolean;
  ariaLabel?: string;
  id?: string;
}) {
  const layoutId = useId();
  return (
    <div
      id={id}
      role={asTabs ? "tablist" : "radiogroup"}
      aria-label={ariaLabel}
      className={cn(
        "inline-flex max-w-full items-center gap-1 overflow-x-auto rounded-full bg-foreground/[0.035] p-1 ring-1 ring-foreground/[0.06] dark:bg-white/[0.04] dark:ring-white/10",
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role={asTabs ? "tab" : "radio"}
            tabIndex={active ? 0 : -1}
            onKeyDown={(event) => {
              const index = options.findIndex((item) => item.value === opt.value);
              const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : ["ArrowRight", "ArrowDown"].includes(event.key) ? (index + 1) % options.length : ["ArrowLeft", "ArrowUp"].includes(event.key) ? (index - 1 + options.length) % options.length : -1;
              if (next < 0) return;
              event.preventDefault();
              onChange(options[next].value);
              const buttons = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("button");
              buttons?.[next]?.focus();
            }}
            id={id ? `${id}-tab-${opt.value}` : undefined}
            aria-controls={asTabs && id ? `${id}-panel-${opt.value}` : undefined}
            aria-selected={asTabs ? active : undefined}
            aria-checked={asTabs ? undefined : active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "relative inline-flex shrink-0 items-center gap-2 rounded-full font-medium transition-colors duration-500 ease-vanguard",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              size === "sm" ? "h-8 px-3.5 text-xs" : "h-9 px-4 text-[13px]",
              active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {active ? (
              <motion.span
                layoutId={layoutId}
                transition={SPRING_SOFT}
                className="absolute inset-0 rounded-full bg-card shadow-[0_1px_2px_hsl(var(--foreground)/0.06),inset_0_1px_0_hsl(0_0%_100%/0.6)] ring-1 ring-foreground/[0.06] dark:bg-white/10 dark:shadow-none dark:ring-white/10"
              />
            ) : null}
            {opt.icon ? <span aria-hidden className="relative">{opt.icon}</span> : null}
            <span className="relative">{opt.label}</span>
            {opt.count !== undefined ? (
              <span className="relative rounded-full bg-foreground/[0.06] px-1.5 text-[10px] tabular-nums text-muted-foreground dark:bg-white/10">{opt.count}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/** Spring toggle switch. */
export function Toggle({
  checked,
  onChange,
  label,
  disabled,
  className,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  /** Accessible name — required when no visible label is associated. */
  label: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-7 w-12 shrink-0 items-center rounded-full p-1 ring-1 transition-colors duration-500 ease-vanguard",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
        checked ? "bg-primary ring-primary" : "bg-foreground/[0.08] ring-foreground/[0.06] dark:bg-white/10 dark:ring-white/10",
        className,
      )}
    >
      <motion.span
        layout
        transition={SPRING_SOFT}
        className={cn("h-5 w-5 rounded-full bg-white shadow-[0_2px_6px_-1px_hsl(0_0%_0%/0.18)]", checked ? "ml-auto" : "mr-auto")}
      />
    </button>
  );
}

/** Selectable chip (filters, multi-select preferences). */
export function Chip({
  active,
  onClick,
  children,
  className,
  disabled,
  icon,
}: {
  active?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
  icon?: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium ring-1 transition-[background-color,color,box-shadow,transform] duration-500 ease-vanguard active:scale-[0.97]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:opacity-50",
        active
          ? "bg-foreground text-background ring-foreground dark:bg-white dark:text-black dark:ring-white"
          : "bg-card text-muted-foreground ring-foreground/[0.08] hover:text-foreground hover:ring-foreground/20 dark:bg-white/[0.03] dark:ring-white/10",
        className,
      )}
    >
      {icon ? <span aria-hidden>{icon}</span> : null}
      {children}
    </button>
  );
}
