"use client";

import { forwardRef, useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Form controls. Inputs sit in a recessed bezel: a hairline tray with an
 * inset core; focus lifts the tray ring to the brand color.
 */
const CONTROL =
  "w-full min-w-0 rounded-[calc(1rem-0.25rem)] bg-card px-4 text-sm text-foreground shadow-bezel-core outline-none dark:bg-background/70 dark:shadow-bezel-core-dark " +
  "placeholder:text-muted-foreground/70 disabled:cursor-not-allowed disabled:opacity-60 transition-[background-color] duration-500 ease-vanguard";

const TRAY =
  "min-w-0 max-w-full rounded-2xl bg-foreground/[0.03] p-1 ring-1 ring-foreground/[0.07] dark:bg-white/[0.03] dark:ring-white/10 " +
  "transition-[box-shadow,background-color] duration-500 ease-vanguard focus-within:ring-2 focus-within:ring-primary/40";

export const inputTrayClass = TRAY;
export const inputControlClass = CONTROL;

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { trayClassName?: string; leading?: ReactNode; trailing?: ReactNode }>(
  ({ className, trayClassName, leading, trailing, ...props }, ref) => (
    <div className={cn(TRAY, (leading || trailing) && "relative", trayClassName)}>
      {leading ? <span aria-hidden className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground">{leading}</span> : null}
      <input ref={ref} className={cn(CONTROL, "h-11", leading && "pl-10", trailing && "pr-12", className)} {...props} />
      {trailing ? <span className="absolute right-2.5 top-1/2 -translate-y-1/2">{trailing}</span> : null}
    </div>
  ),
);
Input.displayName = "VanguardInput";

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement> & { trayClassName?: string }>(
  ({ className, trayClassName, ...props }, ref) => (
    <div className={cn(TRAY, trayClassName)}>
      <textarea ref={ref} className={cn(CONTROL, "min-h-28 resize-y py-3 leading-6", className)} {...props} />
    </div>
  ),
);
Textarea.displayName = "VanguardTextarea";

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement> & { trayClassName?: string }>(
  ({ className, trayClassName, children, ...props }, ref) => (
    <div className={cn(TRAY, "relative", trayClassName)}>
      <select ref={ref} className={cn(CONTROL, "h-11 appearance-none pr-10", className)} {...props}>
        {children}
      </select>
      <svg aria-hidden viewBox="0 0 16 16" className="pointer-events-none absolute right-4 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth="1.25">
        <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  ),
);
Select.displayName = "VanguardSelect";

/**
 * Label + control + hint wrapper. Pass a render function to receive the
 * generated id, or pass `htmlFor` yourself.
 */
export function Field({
  label,
  hint,
  error,
  htmlFor,
  className,
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  htmlFor?: string;
  className?: string;
  children: ReactNode | ((id: string) => ReactNode);
}) {
  const generated = useId();
  const id = htmlFor ?? generated;
  return (
    <div className={cn("space-y-2", className)}>
      <label htmlFor={id} className="block pl-1 text-[12px] font-medium tracking-[-0.005em] text-muted-foreground">
        {label}
      </label>
      {typeof children === "function" ? children(id) : children}
      {error ? (
        <p role="alert" className="pl-1 text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="pl-1 text-xs leading-5 text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
