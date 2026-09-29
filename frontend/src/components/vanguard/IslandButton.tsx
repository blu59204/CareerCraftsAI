"use client";

import Link from "next/link";
import { forwardRef, type ReactNode } from "react";
import { ArrowUpRight } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";

/**
 * Island pill button with the "button-in-button" trailing icon: the icon sits
 * in its own circle flush with the right inner padding, and drifts
 * diagonally + scales on hover. The whole pill compresses on press.
 */
export type IslandTone = "primary" | "ghost" | "quiet" | "danger";
export type IslandSize = "sm" | "md" | "lg";

const TONE: Record<IslandTone, { pill: string; well: string }> = {
  primary: {
    pill: "bg-primary text-primary-foreground ring-1 ring-primary shadow-[inset_0_1px_0_hsl(0_0%_100%/0.18),0_10px_24px_-14px_hsl(var(--primary)/0.7)] hover:bg-primary/90",
    well: "bg-white/15",
  },
  ghost: {
    pill: "bg-card text-foreground ring-1 ring-foreground/10 shadow-bezel-core dark:ring-white/10 dark:shadow-bezel-core-dark hover:bg-muted/60",
    well: "bg-foreground/[0.06] dark:bg-white/10",
  },
  quiet: {
    pill: "bg-transparent text-muted-foreground ring-1 ring-transparent hover:bg-foreground/[0.04] hover:text-foreground dark:hover:bg-white/[0.05]",
    well: "bg-foreground/[0.05] dark:bg-white/10",
  },
  danger: {
    pill: "bg-danger text-white ring-1 ring-danger shadow-[inset_0_1px_0_hsl(0_0%_100%/0.18)] hover:bg-danger/90",
    well: "bg-white/15",
  },
};

const SIZE: Record<IslandSize, { pill: string; withIcon: string; well: string; icon: number }> = {
  sm: { pill: "h-9 gap-2 px-4 text-[13px]", withIcon: "pr-1", well: "h-7 w-7", icon: 14 },
  md: { pill: "h-11 gap-2.5 px-6 text-sm", withIcon: "pr-1.5", well: "h-8 w-8", icon: 15 },
  lg: { pill: "h-14 gap-3 px-7 text-[15px]", withIcon: "pr-2", well: "h-10 w-10", icon: 17 },
};

const BASE =
  "group relative inline-flex select-none items-center justify-center whitespace-nowrap rounded-full font-medium tracking-[-0.01em] " +
  "transition-[background-color,color,box-shadow,transform,opacity] duration-500 ease-vanguard active:scale-[0.98] " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
  "disabled:pointer-events-none disabled:opacity-50";

interface CommonProps {
  tone?: IslandTone;
  size?: IslandSize;
  /** Leading icon element (Phosphor, weight="light"). */
  icon?: ReactNode;
  /** Trailing icon in its own circle. `true` = arrow ↗; pass a node for a custom icon; omit for none. */
  trailing?: ReactNode | true;
  className?: string;
  children?: ReactNode;
}

function Trailing({ trailing, size, tone }: { trailing: ReactNode | true; size: IslandSize; tone: IslandTone }) {
  return (
    <span
      aria-hidden
      className={cn(
        "ml-1 grid shrink-0 place-items-center rounded-full transition-transform duration-500 ease-vanguard",
        "group-hover:translate-x-1 group-hover:-translate-y-[1px] group-hover:scale-105",
        SIZE[size].well,
        TONE[tone].well,
      )}
    >
      {trailing === true ? <ArrowUpRight size={SIZE[size].icon} weight="light" /> : trailing}
    </span>
  );
}

export type IslandButtonProps = CommonProps & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children">;

export const IslandButton = forwardRef<HTMLButtonElement, IslandButtonProps>(
  ({ tone = "primary", size = "md", icon, trailing, className, children, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(BASE, SIZE[size].pill, trailing && SIZE[size].withIcon, TONE[tone].pill, className)}
      {...props}
    >
      {icon ? <span aria-hidden className="-ml-1 grid place-items-center">{icon}</span> : null}
      {children}
      {trailing ? <Trailing trailing={trailing} size={size} tone={tone} /> : null}
    </button>
  ),
);
IslandButton.displayName = "IslandButton";

export type IslandLinkProps = CommonProps & {
  href: string;
  external?: boolean;
} & Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "children">;

/** Same visuals as IslandButton, rendered as a Next.js Link (or <a> when external). */
export function IslandLink({ tone = "primary", size = "md", icon, trailing, className, children, href, external, ...props }: IslandLinkProps) {
  const cls = cn(BASE, SIZE[size].pill, trailing && SIZE[size].withIcon, TONE[tone].pill, className);
  const inner = (
    <>
      {icon ? <span aria-hidden className="-ml-1 grid place-items-center">{icon}</span> : null}
      {children}
      {trailing ? <Trailing trailing={trailing} size={size} tone={tone} /> : null}
    </>
  );
  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={cls} {...props}>
        {inner}
      </a>
    );
  }
  return (
    <Link href={href} className={cls} {...props}>
      {inner}
    </Link>
  );
}

/** Small circular icon-only button (close, remove, show/hide). Always pass `aria-label`. */
export const IconButton = forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { size?: "sm" | "md" }>(
  ({ className, size = "md", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "grid shrink-0 place-items-center rounded-full text-muted-foreground ring-1 ring-foreground/[0.06] dark:ring-white/10",
        "transition-[background-color,color,transform] duration-500 ease-vanguard hover:bg-foreground/[0.05] hover:text-foreground active:scale-[0.94] dark:hover:bg-white/[0.06]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
        size === "sm" ? "h-7 w-7" : "h-9 w-9",
        className,
      )}
      {...props}
    />
  ),
);
IconButton.displayName = "IconButton";
