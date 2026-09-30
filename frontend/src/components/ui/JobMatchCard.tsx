"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, ArrowUpRight, MagnifyingGlass, MapPin, Target } from "@phosphor-icons/react";
import { Bezel, EASE_OUT_EXPO, EmptyPanel, PanelTitle, listItem, listStagger } from "@/components/vanguard";

type Props = {
  jobs: { id: string; company: string; role: string; matchPercent: number; location?: string; jobUrl?: string | null }[];
};

const clamp = (n: number) => Math.max(0, Math.min(100, n));

/** Match meter — grows via scaleX (transform only). */
function MatchMeter({ value }: { value: number }) {
  const reduce = useReducedMotion();
  const scale = clamp(value) / 100;
  return (
    <div aria-hidden className="h-1 w-16 overflow-hidden rounded-full bg-foreground/[0.06] dark:bg-white/10">
      {reduce ? (
        <div className="h-full w-full origin-left rounded-full bg-primary" style={{ transform: `scaleX(${scale})` }} />
      ) : (
        <motion.div
          key={scale}
          className="h-full w-full origin-left rounded-full bg-primary"
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: scale }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: EASE_OUT_EXPO, delay: 0.25 }}
        />
      )}
    </div>
  );
}

function Row({ job }: { job: Props["jobs"][number] }) {
  const initial = job.company.trim().charAt(0).toUpperCase() || "·";
  const content = (
    <>
      <span
        aria-hidden
        className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-foreground/[0.04] font-geist text-sm font-semibold text-foreground/80 ring-1 ring-foreground/[0.06] shadow-bezel-core dark:bg-white/[0.05] dark:ring-white/10 dark:shadow-bezel-core-dark"
      >
        {initial}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium tracking-[-0.01em] text-foreground">{job.role}</span>
        <span className="mt-0.5 flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
          <span className="truncate">{job.company}</span>
          {job.location ? (
            <>
              <span aria-hidden className="text-muted-foreground/50">·</span>
              <MapPin size={12} weight="light" aria-hidden className="shrink-0" />
              <span className="truncate">{job.location}</span>
            </>
          ) : null}
        </span>
      </span>
      <span className="flex shrink-0 flex-col items-end gap-1.5">
        <span className="font-geist text-lg font-semibold leading-none tabular-nums tracking-[-0.03em] text-foreground">
          {job.matchPercent}
          <span className="text-xs font-medium text-muted-foreground">%</span>
          <span className="sr-only"> match</span>
        </span>
        <MatchMeter value={job.matchPercent} />
      </span>
      {job.jobUrl ? (
        <ArrowUpRight
          size={14}
          weight="light"
          aria-hidden
          className="shrink-0 text-muted-foreground transition-transform duration-500 ease-vanguard group-hover:-translate-y-[1px] group-hover:translate-x-0.5 group-hover:text-foreground"
        />
      ) : null}
    </>
  );

  const rowClass =
    "group -mx-3 flex items-center gap-3.5 rounded-2xl px-3 py-3 transition-colors duration-500 ease-vanguard";

  return (
    <motion.li variants={listItem}>
      {job.jobUrl ? (
        <a
          href={job.jobUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={`${rowClass} hover:bg-foreground/[0.035] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/[0.04]`}
        >
          {content}
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      ) : (
        <div className={rowClass}>{content}</div>
      )}
    </motion.li>
  );
}

export function JobMatchCard({ jobs }: Props) {
  return (
    <Bezel size="lg" className="h-full" coreClassName="flex flex-col p-6 md:p-7">
      <PanelTitle
        title="Top job matches"
        icon={<Target size={16} weight="light" />}
        meta={
          <Link
            href="/applications"
            className="group inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs text-muted-foreground transition-colors duration-500 ease-vanguard hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            View all
            <ArrowRight size={12} weight="light" className="transition-transform duration-500 ease-vanguard group-hover:translate-x-0.5" />
          </Link>
        }
      />
      {jobs.length > 0 ? (
        <motion.ul
          className="mt-4 divide-y divide-foreground/[0.06] dark:divide-white/[0.07]"
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.2 }}
          variants={listStagger}
        >
          {jobs.slice(0, 4).map((j) => (
            <Row key={j.id} job={j} />
          ))}
        </motion.ul>
      ) : (
        <EmptyPanel
          compact
          className="my-auto"
          icon={<MagnifyingGlass size={22} weight="light" />}
          title="No saved jobs yet"
          description="Run Search Jobs to find matches, then save the ones worth pursuing."
        />
      )}
    </Bezel>
  );
}
