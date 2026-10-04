'use client'

import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { toast } from 'sonner'
import {
  ArrowSquareOut,
  ChartBar,
  Check,
  Copy,
  HandCoins,
  Hourglass,
  Quotes,
  Scales,
  WarningCircle,
  X,
} from '@phosphor-icons/react'
import { apiClient, getApiErrorMessage } from '@/lib/api'
import { startAgentRun, waitForAgentRun } from '@/lib/agent-run'
import { cn } from '@/lib/utils'
import {
  Bezel,
  EASE_OUT_EXPO,
  EmptyPanel,
  Eyebrow,
  Field,
  Hairline,
  Input,
  IslandButton,
  Notice,
  PanelTitle,
  Screen,
  SectionHeading,
  Skeleton,
  StatusPill,
  listItem,
  listStagger,
  panelSwap,
  inputControlClass,
  inputTrayClass,
  type StatusTone,
} from '@/components/vanguard'
import { LocationInput } from '@/components/ui/LocationInput'

// Matches the shape we render from the salary_intelligence agent's run
// output — see backend/app/agents/salary_agent.py (report + negotiation
// script). `id` is the agent run id, used for the approve/discard actions.
// p90, offer_amount and total_comp are optional: rendered only when the run
// output carries them.
interface SalaryReport {
  id: string
  p25: number
  p50: number
  p75: number
  p90: number | null
  offer_amount: number | null
  total_comp: Array<{ label: string; amount: number }> | null
  classification: 'below_market' | 'at_market' | 'above_market' | null
  negotiation_script: Record<string, unknown> | null
  data_unavailable: boolean
  currency: string
  sample_size: number | null
  sources: string[]
}

type Classification = NonNullable<SalaryReport['classification']>

const CLASSIFICATION: Record<Classification, { label: string; tone: StatusTone }> = {
  below_market: { label: 'Below market', tone: 'danger' },
  at_market: { label: 'At market', tone: 'warning' },
  above_market: { label: 'Above market', tone: 'success' },
}

function formatMoney(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(amount)
  } catch {
    return amount.toLocaleString()
  }
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function parseTotalComp(value: unknown): SalaryReport['total_comp'] {
  if (typeof value === 'number' && value > 0) return [{ label: 'Median total', amount: value }]
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const rows = Object.entries(value as Record<string, unknown>)
      .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && entry[1] > 0)
      .map(([key, amount]) => ({ label: key.replace(/_/g, ' '), amount }))
    return rows.length > 0 ? rows : null
  }
  return null
}

function scriptToText(report: SalaryReport): string {
  const script = report.negotiation_script
  if (!script) return ''
  const parts: string[] = []
  if (typeof script.opening === 'string') parts.push(script.opening)
  if (typeof script.counter_offer === 'number') {
    parts.push(`Counter-offer: ${formatMoney(script.counter_offer, report.currency)}`)
  }
  if (Array.isArray(script.justifications)) {
    parts.push((script.justifications as unknown[]).map((item) => `- ${String(item)}`).join('\n'))
  }
  return parts.join('\n\n')
}

/** Entrance used by the left editorial column (mirrors PageHero's choreography). */
function useEnter() {
  const reduce = useReducedMotion()
  return (delay: number) =>
    reduce
      ? { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.2 } }
      : {
          initial: { opacity: 0, y: 28, filter: 'blur(10px)' },
          animate: { opacity: 1, y: 0, filter: 'blur(0px)', transitionEnd: { filter: 'none' } },
          transition: { duration: 0.9, ease: EASE_OUT_EXPO, delay },
        }
}

// ─────────────────────────────────────────────────────────────────────────────
// Percentile band — every bar is a full-width element scaled on X from the
// left edge, so the only animated property is transform.
// ─────────────────────────────────────────────────────────────────────────────

function ScaleBar({ ratio, delay, className }: { ratio: number; delay: number; className?: string }) {
  const reduce = useReducedMotion()
  const target = Math.min(Math.max(ratio, 0), 1)
  return (
    <motion.span
      aria-hidden
      className={cn('absolute inset-0 origin-left rounded-full', className)}
      initial={{ scaleX: reduce ? target : 0 }}
      animate={{ scaleX: target }}
      transition={reduce ? { duration: 0 } : { duration: 1.1, ease: EASE_OUT_EXPO, delay }}
    />
  )
}

function Marker({
  pct,
  label,
  tone,
  side,
}: {
  pct: number
  label: string
  tone: 'primary' | 'foreground'
  side: 'above' | 'below'
}) {
  const clamped = Math.min(Math.max(pct, 0), 100)
  const align = clamped > 85 ? '-translate-x-full' : clamped < 15 ? 'translate-x-0' : '-translate-x-1/2'
  return (
    <div className="pointer-events-none absolute inset-y-0" style={{ left: `${clamped}%` }}>
      <span
        aria-hidden
        className={cn(
          'absolute -bottom-1 -top-1 w-px -translate-x-1/2',
          tone === 'primary' ? 'bg-primary' : 'bg-foreground/70 dark:bg-white/70',
        )}
      />
      <span
        className={cn(
          'absolute whitespace-nowrap text-[11px] font-medium tabular-nums',
          side === 'below' ? 'top-full mt-2.5' : 'bottom-full mb-2.5',
          align,
          tone === 'primary' ? 'text-primary' : 'text-foreground/80',
        )}
      >
        {label}
      </span>
    </div>
  )
}

function PercentileBand({ report }: { report: SalaryReport }) {
  const domain = Math.max(report.p75, report.p90 ?? 0, report.offer_amount ?? 0, 1)
  const pct = (value: number) => (value / domain) * 100
  const rows: Array<{ key: 'p25' | 'p50' | 'p75' | 'p90'; caption: string; value: number }> = [
    { key: 'p25', caption: 'Lower quartile', value: report.p25 },
    { key: 'p50', caption: 'Median', value: report.p50 },
    { key: 'p75', caption: 'Upper quartile', value: report.p75 },
    ...(report.p90 ? [{ key: 'p90' as const, caption: 'Top decile', value: report.p90 }] : []),
  ]
  const iqrStart = pct(report.p25)
  const iqrWidth = Math.max(pct(report.p75) - iqrStart, 0.5)

  return (
    <div className="space-y-10">
      {/* Range strip: interquartile band with median + offer markers */}
      <figure className="space-y-3">
        <figcaption className="flex items-baseline justify-between gap-3 text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
          <span>Interquartile range</span>
          <span className="normal-case tracking-normal tabular-nums">
            {formatMoney(report.p25, report.currency)} – {formatMoney(report.p75, report.currency)}
          </span>
        </figcaption>
        <div className={cn('pb-8', report.offer_amount !== null && 'pt-7')}>
          <div className="relative h-10 rounded-full bg-foreground/[0.04] ring-1 ring-foreground/[0.06] dark:bg-white/[0.04] dark:ring-white/10">
            <div className="absolute inset-y-1.5 overflow-hidden rounded-full" style={{ left: `${iqrStart}%`, width: `${iqrWidth}%` }}>
              <ScaleBar ratio={1} delay={0.15} className="bg-primary/20 ring-1 ring-inset ring-primary/30" />
            </div>
            <Marker pct={pct(report.p50)} label={`Median ${formatMoney(report.p50, report.currency)}`} tone="primary" side="below" />
            {report.offer_amount !== null ? (
              <Marker
                pct={pct(report.offer_amount)}
                label={`Your offer ${formatMoney(report.offer_amount, report.currency)}`}
                tone="foreground"
                side="above"
              />
            ) : null}
          </div>
        </div>
      </figure>

      {/* Individual percentile bars */}
      <ul className="space-y-5">
        {rows.map((row, i) => (
          <li key={row.key} className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-x-4 gap-y-2 sm:grid-cols-[5.5rem_minmax(0,1fr)_8.5rem]">
            <div className="min-w-0">
              <p className="font-geist-mono text-xs uppercase tracking-[0.08em] text-foreground">{row.key}</p>
              <p className="truncate text-[11px] text-muted-foreground">{row.caption}</p>
            </div>
            <div className="relative h-2.5 overflow-hidden rounded-full bg-foreground/[0.05] dark:bg-white/[0.06]">
              <ScaleBar
                ratio={row.value / domain}
                delay={0.2 + i * 0.08}
                className={row.key === 'p50' ? 'bg-primary' : 'bg-foreground/25 dark:bg-white/30'}
              />
            </div>
            <span
              data-testid="salary-percentile-value"
              className="col-start-2 font-geist-mono text-sm tabular-nums text-foreground sm:col-start-auto sm:text-right"
            >
              {formatMoney(row.value, report.currency)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Right-column states
// ─────────────────────────────────────────────────────────────────────────────

function IdlePanel() {
  const schematic = [0.42, 0.6, 0.78, 0.94]
  return (
    <Bezel coreClassName="px-6 py-8 md:px-10 md:py-12">
      <div aria-hidden className="mx-auto max-w-md space-y-4 opacity-60">
        {schematic.map((ratio, i) => (
          <div key={ratio} className="grid grid-cols-[3rem_minmax(0,1fr)] items-center gap-4">
            <span className="font-geist-mono text-[11px] uppercase text-muted-foreground">{['p25', 'p50', 'p75', 'p90'][i]}</span>
            <div className="relative h-2 overflow-hidden rounded-full bg-foreground/[0.05] dark:bg-white/[0.06]">
              <ScaleBar ratio={ratio} delay={0.1 + i * 0.08} className={i === 1 ? 'bg-primary/40' : 'bg-foreground/[0.12] dark:bg-white/15'} />
            </div>
          </div>
        ))}
      </div>
      <EmptyPanel
        compact
        className="pt-10"
        title="Your percentile band lands here"
        description="Enter a role and, ideally, a location. The agent reads published salary pages and derives the band from the figures it finds."
      />
      <Hairline className="my-6" />
      <ul className="grid gap-4 text-sm leading-6 text-muted-foreground md:grid-cols-3">
        <li>
          <span className="block font-medium text-foreground">Real figures only</span>
          Fewer than three published salaries returns “not enough data”, never a guess.
        </li>
        <li>
          <span className="block font-medium text-foreground">Offer check</span>
          Add the offer you received to see if it sits below, at or above market.
        </li>
        <li>
          <span className="block font-medium text-foreground">You approve</span>
          The drafted script waits for your review before it is finalized.
        </li>
      </ul>
    </Bezel>
  )
}

function PendingPanel() {
  return (
    <Bezel coreClassName="space-y-8 p-6 md:p-8">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <Hourglass size={18} weight="light" aria-hidden />
        <p>Reading published salary pages and deriving percentiles. This can take up to two minutes.</p>
      </div>
      <div className="space-y-3">
        <Skeleton className="h-4 w-40 rounded-full" />
        <Skeleton className="h-14 w-2/3 rounded-2xl" />
      </div>
      <Skeleton className="h-10 w-full rounded-full" />
      <div className="space-y-5">
        {[0.5, 0.7, 0.85].map((w) => (
          <div key={w} className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-4">
            <Skeleton className="h-3 w-10 rounded-full" />
            <Skeleton className="h-2.5 rounded-full" />
          </div>
        ))}
      </div>
      <Skeleton className="h-40 w-full" />
    </Bezel>
  )
}

function UnavailablePanel({ report }: { report: SalaryReport }) {
  return (
    <Bezel tone="muted" coreClassName="space-y-6 p-6 md:p-8">
      <Notice tone="warning" icon={<WarningCircle size={18} weight="light" />}>
        Not enough published salary figures were found for this role. Try a more common title
        (for example &ldquo;Backend Engineer&rdquo;), add a location, or leave the company out to see the wider market.
      </Notice>
      {report.sources.length > 0 ? (
        <div className="space-y-3">
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Pages checked</p>
          <SourceLinks sources={report.sources} />
        </div>
      ) : null}
    </Bezel>
  )
}

function SourceLinks({ sources }: { sources: string[] }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {sources.map((url) => (
        <li key={url}>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full bg-foreground/[0.03] px-3 py-1.5 text-xs text-muted-foreground ring-1 ring-foreground/[0.07] transition-colors duration-500 ease-vanguard hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-white/[0.03] dark:ring-white/10"
          >
            {hostname(url)}
            <ArrowSquareOut size={12} weight="light" aria-hidden />
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        </li>
      ))}
    </ul>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────

export default function SalaryPage() {
  const [role, setRole] = useState('')
  const [company, setCompany] = useState('')
  const [location, setLocation] = useState('')
  const [experienceYears, setExperienceYears] = useState('')
  const [offerAmount, setOfferAmount] = useState('')
  const [report, setReport] = useState<SalaryReport | null>(null)
  const [copied, setCopied] = useState(false)
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const enter = useEnter()

  useEffect(() => () => {
    if (copyTimer.current) clearTimeout(copyTimer.current)
  }, [])

  // The agent can run up to 120s server-side, so we start it and poll for a
  // terminal status instead of holding one long HTTP request open. Data-rich
  // runs land in "awaiting_approval" (HITL gate on the negotiation script);
  // "data_unavailable" runs land in "completed" with a flat result.
  const mutation = useMutation({
    mutationFn: async (data: {
      role: string
      company?: string
      location?: string
      experience_years?: number
      offer_amount?: number
    }) => {
      const runId = await startAgentRun('salary_intelligence', data)
      const run = await waitForAgentRun(runId)
      if (run.status !== 'completed' && run.status !== 'awaiting_approval') {
        throw new Error(run.error || `Salary report ${run.status}`)
      }
      const output = (run.output ?? {}) as Record<string, unknown>
      const reportData = (output.report as Record<string, unknown> | undefined) ?? output
      const script = (output.script as Record<string, unknown> | undefined) ?? null
      const p90 = Number(reportData.p90 ?? 0)
      const result: SalaryReport = {
        id: runId,
        p25: Number(reportData.p25 ?? 0),
        p50: Number(reportData.p50 ?? 0),
        p75: Number(reportData.p75 ?? 0),
        p90: Number.isFinite(p90) && p90 > 0 ? p90 : null,
        offer_amount: typeof reportData.offer_amount === 'number' ? reportData.offer_amount : null,
        total_comp: parseTotalComp(reportData.total_comp),
        classification: (reportData.classification as SalaryReport['classification']) ?? null,
        negotiation_script: script,
        data_unavailable: Boolean(reportData.data_unavailable),
        currency: String(reportData.currency ?? 'USD'),
        sample_size: typeof reportData.sample_size === 'number' ? reportData.sample_size : null,
        sources: Array.isArray(reportData.data_sources) ? (reportData.data_sources as string[]) : [],
      }
      return result
    },
    onSuccess: (data) => {
      setReport(data)
      if (data.data_unavailable) {
        toast.warning('Not enough market data found for this role')
      } else {
        toast.success('Salary report generated')
      }
    },
    onError: (error) => toast.error(getApiErrorMessage(error, error instanceof Error ? error.message : 'Failed to generate report')),
  })

  const approveMutation = useMutation({
    mutationFn: (reportId: string) =>
      apiClient.post(`/agents/${reportId}/approve`, { approved: true }),
    onSuccess: () => toast.success('Negotiation script approved'),
    onError: (error) => toast.error(getApiErrorMessage(error, 'Approval failed')),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!role.trim()) return toast.error('Role is required')
    mutation.mutate({
      role,
      ...(company && { company }),
      ...(location && { location }),
      ...(experienceYears && { experience_years: Number(experienceYears) }),
      ...(offerAmount && { offer_amount: Number(offerAmount) }),
    })
  }

  const handleCopyScript = async (current: SalaryReport) => {
    const text = scriptToText(current)
    if (!text) {
      toast.error('There is no script to copy yet')
      return
    }
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      toast.success('Script copied to clipboard')
      if (copyTimer.current) clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Copy failed. Select the text and copy it manually.')
    }
  }

  const view: 'idle' | 'pending' | 'unavailable' | 'report' = mutation.isPending
    ? 'pending'
    : !report
      ? 'idle'
      : report.data_unavailable
        ? 'unavailable'
        : 'report'

  const approved = approveMutation.isSuccess && report !== null && approveMutation.variables === report.id

  const status: { tone: StatusTone; label: string; live: boolean } =
    view === 'pending'
      ? { tone: 'primary', label: 'Researching the market', live: true }
      : view === 'unavailable'
        ? { tone: 'warning', label: 'Not enough data', live: false }
        : view === 'report'
          ? approved
            ? { tone: 'success', label: 'Script approved', live: false }
            : { tone: 'warning', label: 'Awaiting your review', live: true }
          : { tone: 'neutral', label: 'No report yet', live: false }

  return (
    <Screen>
      <div className="grid grid-cols-1 gap-6 pt-2 md:pt-4 lg:grid-cols-12 lg:gap-8">
        {/* ── Left: editorial headline + benchmark form ─────────────────── */}
        <div className="min-w-0 lg:sticky lg:top-6 lg:col-span-5 lg:self-start">
          <motion.div {...enter(0)}>
            <Eyebrow>Compensation</Eyebrow>
          </motion.div>
          <motion.h1
            {...enter(0.06)}
            className="mt-4 text-balance font-geist text-[clamp(2rem,3.5vw,3.5rem)] font-semibold leading-[1.05] tracking-[-0.04em] text-foreground"
          >
            Salary
            <span className="block text-muted-foreground/70">intelligence.</span>
          </motion.h1>
          <motion.p {...enter(0.12)} className="mt-5 max-w-[46ch] text-pretty text-[15px] leading-7 text-muted-foreground">
            Benchmark an offer against published market figures, see where it lands, and review a counter-offer script before you use it.
          </motion.p>

          <motion.div {...enter(0.18)} className="mt-8">
            <Bezel lifted coreClassName="p-5 md:p-6">
              <form onSubmit={handleSubmit} className="space-y-5" aria-label="Salary benchmark">
                <Field label="Target role">
                  {(id) => (
                    <Input
                      id={id}
                      type="text"
                      name="role"
                      placeholder="Role *"
                      value={role}
                      onChange={(e) => setRole(e.target.value)}
                      autoComplete="organization-title"
                      required
                    />
                  )}
                </Field>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Field label="Company">
                    {(id) => (
                      <Input
                        id={id}
                        type="text"
                        name="company"
                        placeholder="Company (optional)"
                        value={company}
                        onChange={(e) => setCompany(e.target.value)}
                        autoComplete="organization"
                      />
                    )}
                  </Field>
                  <Field label="Location">
                    {(id) => (
                      <div className={inputTrayClass}>
                        <LocationInput
                          id={id}
                          name="location"
                          placeholder="City or Remote (optional)"
                          value={location}
                          onChange={setLocation}
                          inputClassName={cn(inputControlClass, "h-11")}
                        />
                      </div>
                    )}
                  </Field>
                  <Field label="Experience (years)">
                    {(id) => (
                      <Input
                        id={id}
                        type="number"
                        name="experience_years"
                        inputMode="numeric"
                        min={0}
                        max={60}
                        placeholder="Years of experience (optional)"
                        value={experienceYears}
                        onChange={(e) => setExperienceYears(e.target.value)}
                        className="tabular-nums"
                      />
                    )}
                  </Field>
                  <Field label="Offer received">
                    {(id) => (
                      <Input
                        id={id}
                        type="number"
                        name="offer_amount"
                        inputMode="numeric"
                        min={0}
                        placeholder="Your offer, annual (optional)"
                        value={offerAmount}
                        onChange={(e) => setOfferAmount(e.target.value)}
                        className="tabular-nums"
                      />
                    )}
                  </Field>
                </div>
                <IslandButton
                  type="submit"
                  size="lg"
                  disabled={mutation.isPending}
                  className="w-full"
                  trailing={
                    mutation.isPending ? (
                      <Hourglass size={17} weight="light" />
                    ) : (
                      <ChartBar size={17} weight="light" />
                    )
                  }
                >
                  {mutation.isPending ? 'Generating...' : 'Benchmark & Generate Report'}
                </IslandButton>
              </form>
            </Bezel>
          </motion.div>
        </div>

        {/* ── Right: results ─────────────────────────────────────────────── */}
        <section aria-label="Salary report" className="min-w-0 space-y-6 lg:col-span-7 lg:pt-2">
          <motion.div {...enter(0.24)}>
            <SectionHeading
              eyebrow="Report"
              title="Where the market sits"
              actions={
                <div role="status" aria-live="polite">
                  <StatusPill tone={status.tone} live={status.live}>
                    {status.label}
                  </StatusPill>
                </div>
              }
            />
          </motion.div>

          <AnimatePresence mode="wait">
            <motion.div key={view} variants={panelSwap} initial="hidden" animate="show" exit="exit">
              {view === 'idle' ? <IdlePanel /> : null}
              {view === 'pending' ? <PendingPanel /> : null}
              {view === 'unavailable' && report ? <UnavailablePanel report={report} /> : null}

              {view === 'report' && report ? (
                <motion.div variants={listStagger} initial="hidden" animate="show" className="space-y-4">
                  {/* Percentile band */}
                  <motion.div variants={listItem}>
                    <Bezel tone="primary" lifted coreClassName="space-y-8 p-6 md:p-8">
                      <PanelTitle
                        icon={<ChartBar size={16} weight="light" />}
                        title="Market Percentiles"
                        meta={report.sample_size ? `Annual, from ${report.sample_size} published figures` : 'Annual'}
                      />
                      <div>
                        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Median annual pay · p50</p>
                        <p className="mt-3 font-geist text-5xl font-semibold tabular-nums tracking-[-0.04em] text-foreground md:text-6xl">
                          {formatMoney(report.p50, report.currency)}
                        </p>
                      </div>
                      <PercentileBand report={report} />
                      {report.sources.length > 0 ? (
                        <>
                          <Hairline />
                          <div className="space-y-3">
                            <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Sources</p>
                            <SourceLinks sources={report.sources} />
                          </div>
                        </>
                      ) : null}
                    </Bezel>
                  </motion.div>

                  {/* Total comp + offer position */}
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <motion.div variants={listItem}>
                      <Bezel size="md" coreClassName="space-y-5 p-6">
                        <PanelTitle icon={<HandCoins size={16} weight="light" />} title="Total compensation" />
                        {report.total_comp ? (
                          <dl className="space-y-3">
                            {report.total_comp.map((row) => (
                              <div key={row.label} className="flex items-baseline justify-between gap-4">
                                <dt className="text-sm capitalize text-muted-foreground">{row.label}</dt>
                                <dd className="font-geist-mono text-sm tabular-nums text-foreground">{formatMoney(row.amount, report.currency)}</dd>
                              </div>
                            ))}
                          </dl>
                        ) : (
                          <div>
                            <p className="font-geist text-2xl font-semibold tabular-nums tracking-[-0.03em] text-foreground">
                              {formatMoney(report.p25, report.currency)} – {formatMoney(report.p75, report.currency)}
                            </p>
                            <p className="mt-2 text-xs leading-5 text-muted-foreground">
                              Base pay, p25 to p75. The sources did not publish bonus or equity, so total compensation is not estimated.
                            </p>
                          </div>
                        )}
                      </Bezel>
                    </motion.div>

                    <motion.div variants={listItem}>
                      <Bezel size="md" coreClassName="space-y-5 p-6">
                        <PanelTitle
                          icon={<Scales size={16} weight="light" />}
                          title="Your offer"
                          meta={
                            report.classification ? (
                              <StatusPill tone={CLASSIFICATION[report.classification]?.tone ?? 'neutral'}>
                                {CLASSIFICATION[report.classification]?.label ?? report.classification.replace('_', ' ')}
                              </StatusPill>
                            ) : null
                          }
                        />
                        {report.offer_amount !== null ? (
                          <div>
                            <p className="font-geist text-2xl font-semibold tabular-nums tracking-[-0.03em] text-foreground">
                              {formatMoney(report.offer_amount, report.currency)}
                            </p>
                            {report.p50 > 0 ? (
                              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                                <span className="tabular-nums text-foreground">
                                  {report.offer_amount >= report.p50 ? '+' : '−'}
                                  {Math.abs(((report.offer_amount - report.p50) / report.p50) * 100).toFixed(1)}%
                                </span>{' '}
                                versus the market median.
                              </p>
                            ) : null}
                          </div>
                        ) : (
                          <p className="text-sm leading-6 text-muted-foreground">
                            Add the offer you received and run the benchmark again to see whether it sits below, at or above this market.
                          </p>
                        )}
                      </Bezel>
                    </motion.div>
                  </div>

                  {/* Negotiation script + HITL gate */}
                  <motion.div variants={listItem}>
                    <Bezel coreClassName="p-6 md:p-8">
                      <div className="flex items-center justify-between gap-3">
                        <PanelTitle icon={<Quotes size={16} weight="light" />} title="Negotiation Script" />
                        {report.negotiation_script ? (
                          <IslandButton
                            tone="quiet"
                            size="sm"
                            icon={copied ? <Check size={14} weight="light" /> : <Copy size={14} weight="light" />}
                            onClick={() => handleCopyScript(report)}
                            aria-label="Copy script to clipboard"
                          >
                            {copied ? 'Copied' : 'Copy'}
                          </IslandButton>
                        ) : null}
                      </div>

                      <div className="mt-6">
                        {report.negotiation_script ? (
                          <div className="space-y-6">
                            {typeof report.negotiation_script.opening === 'string' && (
                              <p className="max-w-[65ch] whitespace-pre-wrap text-pretty text-[17px] leading-8 tracking-[-0.01em] text-foreground/90">
                                {report.negotiation_script.opening}
                              </p>
                            )}
                            {typeof report.negotiation_script.counter_offer === 'number' && (
                              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 rounded-2xl bg-primary/[0.06] px-5 py-4 ring-1 ring-primary/15">
                                <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-primary">Counter-offer</span>
                                <span className="font-geist text-2xl font-semibold tabular-nums tracking-[-0.03em] text-foreground">
                                  {formatMoney(report.negotiation_script.counter_offer, report.currency)}
                                </span>
                                <span className="text-xs text-muted-foreground">anchored at p75</span>
                              </div>
                            )}
                            {Array.isArray(report.negotiation_script.justifications) && (
                              <ul className="space-y-3">
                                {(report.negotiation_script.justifications as unknown[]).map((item, i) => (
                                  <li key={i} className="flex gap-3 text-sm leading-6 text-muted-foreground">
                                    <span aria-hidden className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/70" />
                                    <span className="max-w-[65ch]">{String(item)}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ) : (
                          <p className="text-sm text-muted-foreground">No script was returned for this run.</p>
                        )}
                      </div>

                      <Hairline className="my-6" />

                      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <p className="max-w-[44ch] text-xs leading-5 text-muted-foreground">
                          This run is paused for your review. Approving marks the script as final for this run. Nothing is sent to anyone.
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <IslandButton
                            tone="ghost"
                            icon={<X size={15} weight="light" />}
                            onClick={() => toast.info('Script discarded')}
                          >
                            Discard
                          </IslandButton>
                          <IslandButton
                            onClick={() => approveMutation.mutate(report.id)}
                            disabled={approveMutation.isPending}
                            trailing={<Check size={15} weight="light" />}
                          >
                            {approveMutation.isPending ? 'Approving...' : 'Approve & Use'}
                          </IslandButton>
                        </div>
                      </div>
                    </Bezel>
                  </motion.div>
                </motion.div>
              ) : null}
            </motion.div>
          </AnimatePresence>
        </section>
      </div>
    </Screen>
  )
}
