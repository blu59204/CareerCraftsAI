"use client";

import Link from "next/link";
import { ArrowDownRight, ArrowRight, ArrowUpRight } from "@phosphor-icons/react";
import { Bezel } from "@/components/vanguard";

type Props = {
  label: string;
  value: string | number;
  trend?: { delta: string; direction: "up" | "down" };
  icon?: React.ReactNode;
  href?: string;
};

/**
 * Single metric in a Double-Bezel enclosure. For rows of metrics prefer the
 * kit's `StatStrip`; this is for a standalone, optionally linked, metric.
 */
export function MetricCard({ label, value, trend, icon, href }: Props) {
  const inner = (
    <Bezel
      size="md"
      className="transition-transform duration-500 ease-vanguard group-hover:-translate-y-0.5"
      coreClassName="p-5 md:p-6"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">{label}</span>
        <span className="flex items-center gap-1.5 text-muted-foreground">
          {icon}
          {href ? (
            <ArrowRight
              size={14}
              weight="light"
              aria-hidden
              className="opacity-0 transition-[opacity,transform] duration-500 ease-vanguard group-hover:translate-x-0.5 group-hover:opacity-100 group-focus-visible:opacity-100"
            />
          ) : null}
        </span>
      </div>
      <p className="mt-4 font-geist text-3xl font-semibold tabular-nums tracking-[-0.04em] text-foreground md:text-4xl">{value}</p>
      {trend && trend.delta ? (
        <p className={`mt-2 inline-flex items-center gap-1 text-xs tabular-nums ${trend.direction === "up" ? "text-success" : "text-danger"}`}>
          {trend.direction === "up" ? (
            <ArrowUpRight size={12} weight="light" aria-hidden />
          ) : (
            <ArrowDownRight size={12} weight="light" aria-hidden />
          )}
          <span className="sr-only">{trend.direction === "up" ? "Up" : "Down"} </span>
          {trend.delta}
        </p>
      ) : null}
    </Bezel>
  );

  if (href) {
    return (
      <Link href={href} className="group block rounded-[1.5rem] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        {inner}
      </Link>
    );
  }
  return <div className="group">{inner}</div>;
}
