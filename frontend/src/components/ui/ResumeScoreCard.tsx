"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUpRight, FileText } from "@phosphor-icons/react";
import { Bezel, EASE_OUT_EXPO, PanelTitle } from "@/components/vanguard";

type Props = {
  /** null: no resume scored yet. */
  atsScore: number | null;
  /** null: nothing to measure keywords against (no saved jobs with a description). */
  keywordCoverage: number | null;
  missingKeywords: string[];
};

const RING_RADIUS = 44;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

const clamp = (n: number) => Math.max(0, Math.min(100, n));

/** Static ATS gauge; the panel's reveal animates it in (no stroke animation — transform/opacity only). */
function ScoreRing({ score }: { score: number | null }) {
  const pct = score === null ? 0 : clamp(score);
  return (
    <div className="relative grid h-28 w-28 shrink-0 place-items-center">
      <svg aria-hidden viewBox="0 0 100 100" className="absolute inset-0 h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={RING_RADIUS} fill="none" strokeWidth="5" className="stroke-foreground/[0.07] dark:stroke-white/10" />
        {score !== null ? (
          <circle
            cx="50"
            cy="50"
            r={RING_RADIUS}
            fill="none"
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={RING_CIRCUMFERENCE}
            strokeDashoffset={RING_CIRCUMFERENCE * (1 - pct / 100)}
            className="stroke-primary"
          />
        ) : null}
      </svg>
      <div className="relative text-center">
        <p className="font-geist text-[2rem] font-semibold leading-none tabular-nums tracking-[-0.04em] text-foreground">
          {score === null ? "—" : score}
        </p>
        <p className="mt-1 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">/ 100</p>
      </div>
    </div>
  );
}

/** Horizontal meter that grows with a transform (scaleX), never width. */
function Meter({ value }: { value: number | null }) {
  const reduce = useReducedMotion();
  const scale = value === null ? 0 : clamp(value) / 100;
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-foreground/[0.06] dark:bg-white/10">
      {reduce ? (
        <div className="h-full w-full origin-left rounded-full bg-primary" style={{ transform: `scaleX(${scale})` }} />
      ) : (
        <motion.div
          key={scale}
          className="h-full w-full origin-left rounded-full bg-primary"
          initial={{ scaleX: 0 }}
          whileInView={{ scaleX: scale }}
          viewport={{ once: true }}
          transition={{ duration: 1.1, ease: EASE_OUT_EXPO, delay: 0.2 }}
        />
      )}
    </div>
  );
}

const inlineLink =
  "font-medium text-primary underline decoration-primary/30 underline-offset-4 transition-colors duration-500 ease-vanguard hover:decoration-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm";

export function ResumeScoreCard({ atsScore, keywordCoverage, missingKeywords }: Props) {
  return (
    <Bezel size="lg" coreClassName="p-6 md:p-7">
      <PanelTitle
        title="Resume score"
        icon={<FileText size={16} weight="light" />}
        meta={
          <Link
            href="/resume"
            className="group inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs text-muted-foreground transition-colors duration-500 ease-vanguard hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Open
            <ArrowUpRight size={12} weight="light" className="transition-transform duration-500 ease-vanguard group-hover:-translate-y-[1px] group-hover:translate-x-0.5" />
          </Link>
        }
      />

      <div className="mt-6 flex items-center gap-6">
        <ScoreRing score={atsScore} />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Keyword coverage</p>
          <p className="mt-2 font-geist text-2xl font-semibold tabular-nums tracking-[-0.03em] text-foreground">
            {keywordCoverage === null ? "—" : `${keywordCoverage}%`}
          </p>
          <div className="mt-3">
            <Meter value={keywordCoverage} />
          </div>
        </div>
      </div>

      {atsScore === null ? (
        <p className="mt-6 text-sm leading-6 text-muted-foreground">
          <Link href="/resume" className={inlineLink}>
            Upload your resume
          </Link>{" "}
          to get a score.
        </p>
      ) : keywordCoverage === null ? (
        <p className="mt-6 text-sm leading-6 text-muted-foreground">
          Scored on readability and format.{" "}
          <Link href="/jobs" className={inlineLink}>
            Save jobs
          </Link>{" "}
          to see which of their keywords your resume is missing.
        </p>
      ) : missingKeywords.length > 0 ? (
        <div className="mt-6">
          <p className="text-xs text-muted-foreground">Missing from your saved jobs</p>
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {missingKeywords.slice(0, 8).map((k) => (
              <li
                key={k}
                className="rounded-full bg-foreground/[0.04] px-2.5 py-1 text-xs text-foreground/80 ring-1 ring-foreground/[0.06] dark:bg-white/[0.05] dark:ring-white/10"
              >
                {k}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Bezel>
  );
}
