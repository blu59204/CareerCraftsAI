'use client'

import { useEffect, useState, type FormEvent } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { motion, useReducedMotion, type Variants } from 'motion/react'
import { toast } from 'sonner'
import {
  ArrowClockwise,
  ArrowUpRight,
  Buildings,
  Code,
  GlobeHemisphereWest,
  Handshake,
  MagnifyingGlass,
  Newspaper,
  Smiley,
  SmileyMeh,
  SmileySad,
  Timer,
  UsersThree,
  WarningCircle,
} from '@phosphor-icons/react'
import { apiClient, getApiErrorMessage } from '@/lib/api'
import { startAgentRun, waitForAgentRun } from '@/lib/agent-run'
import { cn } from '@/lib/utils'
import {
  Bezel,
  EmptyPanel,
  Hairline,
  IslandButton,
  Notice,
  PageHero,
  PanelTitle,
  RevealGroup,
  Screen,
  Section,
  SectionHeading,
  Skeleton,
  StatusPill,
  listItem,
  listStagger,
  reveal,
  type StatusTone,
} from '@/components/vanguard'

interface CompanyNewsItem {
  title?: string
  url?: string
  snippet?: string
  published?: string
}

// Matches the company_research agent's output (CompanyIntel.to_dict() /
// CompanyIntelModel row) — see backend/app/agents/company_research_agent.py.
interface CompanyData {
  company_name: string
  overview: string
  culture_summary: string
  news_items: CompanyNewsItem[]
  tech_stack: string[]
  glassdoor_sentiment: string
  researched_at: string
  partial_data?: Record<string, string> | null
}

const SOURCE_LABELS: Record<string, string> = {
  website: 'overview',
  news: 'news',
  tech_stack: 'tech stack',
  glassdoor: 'employee reviews',
}

const SOURCE_KEYS = Object.keys(SOURCE_LABELS)

function missingSources(partial: Record<string, string> | null | undefined): string[] {
  return partial ? Object.keys(partial).map((key) => SOURCE_LABELS[key] ?? key) : []
}

// Plain fade used in place of the blur/translate reveal under reduced motion.
const fadeOnly: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.2 } },
}

interface RunState {
  tone: StatusTone
  label: string
  live: boolean
  detail: string
}

/** Ticking mm:ss counter for an in-flight agent run. Remount (via `key`) to reset. */
function ElapsedClock() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => window.clearInterval(id)
  }, [])
  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  return (
    <span className="font-geist-mono tabular-nums">
      {mm}:{ss}
    </span>
  )
}

/** Splits a paragraph into a first-sentence lead and the remaining body. */
function splitLead(text: string): { lead: string; rest: string } {
  const trimmed = text.trim()
  const match = trimmed.match(/^(.+?[.!?])\s+([\s\S]+)$/)
  if (!match) return { lead: trimmed, rest: '' }
  return { lead: match[1], rest: match[2] }
}

const SENTIMENT_SCALE = [
  { value: 'negative', label: 'Negative', tone: 'bg-danger', text: 'text-danger' },
  { value: 'neutral', label: 'Neutral', tone: 'bg-foreground/60 dark:bg-white/60', text: 'text-foreground' },
  { value: 'positive', label: 'Positive', tone: 'bg-success', text: 'text-success' },
] as const

function SentimentIcon({ value }: { value: string }) {
  if (value === 'positive') return <Smiley size={40} weight="light" />
  if (value === 'negative') return <SmileySad size={40} weight="light" />
  return <SmileyMeh size={40} weight="light" />
}

/** Bento-shaped placeholder shown while the first briefing is being fetched. */
function BriefingSkeleton() {
  return (
    <Section aria-label="Loading company briefing">
      <div aria-busy="true" className="space-y-4">
        <Skeleton className="h-6 w-24 rounded-full" />
        <Skeleton className="h-9 w-72 max-w-full" />
        <Skeleton className="h-4 w-56 max-w-full" />
      </div>
      <div aria-busy="true" className="grid grid-cols-1 gap-6 md:grid-cols-12">
        <Bezel tone="primary" className="md:col-span-12 lg:col-span-8" coreClassName="space-y-4 p-7 md:p-10">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-11/12" />
          <Skeleton className="h-5 w-4/5" />
          <Skeleton className="h-5 w-2/3" />
        </Bezel>
        <Bezel className="md:col-span-12 lg:col-span-4" coreClassName="space-y-5 p-7">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </Bezel>
        <Bezel className="md:col-span-7" coreClassName="space-y-4 p-7 md:p-8">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-3/4" />
        </Bezel>
        <Bezel className="md:col-span-5" coreClassName="space-y-4 p-7 md:p-8">
          <Skeleton className="h-8 w-44" />
          <Skeleton className="h-14 w-32" />
          <Skeleton className="h-3 w-full rounded-full" />
        </Bezel>
        <Bezel className="md:col-span-5 lg:col-span-4" coreClassName="space-y-4 p-7">
          <Skeleton className="h-8 w-28" />
          <div className="flex flex-wrap gap-2">
            <Skeleton className="h-7 w-16 rounded-full" />
            <Skeleton className="h-7 w-20 rounded-full" />
            <Skeleton className="h-7 w-14 rounded-full" />
            <Skeleton className="h-7 w-24 rounded-full" />
          </div>
        </Bezel>
        <Bezel className="md:col-span-7 lg:col-span-8" coreClassName="space-y-5 p-7 md:p-8">
          <Skeleton className="h-8 w-36" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </Bezel>
      </div>
    </Section>
  )
}

export default function CompanyResearchPage() {
  const [query, setQuery] = useState('')
  const [company, setCompany] = useState('')
  const reduceMotion = useReducedMotion()

  // Restores a previously saved result (fast DB read) while the agent run
  // (up to 120s) is in flight, or if there's nothing new to research.
  const { data, isLoading } = useQuery<CompanyData>({
    queryKey: ['company-intel', company],
    queryFn: () => apiClient.get(`/company/${encodeURIComponent(company)}/intel`).then(r => r.data),
    enabled: !!company,
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: async (forceRefresh: boolean) => {
      const runId = await startAgentRun('company_research', {
        company_name: query || company,
        force_refresh: forceRefresh,
      })
      const run = await waitForAgentRun(runId)
      if (run.status !== 'completed' && run.status !== 'awaiting_approval') {
        throw new Error(run.error || `Company research ${run.status}`)
      }
      return run.output as unknown as CompanyData
    },
    onSuccess: (res) => {
      setCompany(res.company_name)
      const failedSources = missingSources(res.partial_data)
      if (failedSources.length) {
        toast.warning(`Nothing found for: ${failedSources.join(', ')}`)
      }
    },
    onError: (error) => toast.error(getApiErrorMessage(error, error instanceof Error ? error.message : 'Research failed')),
  })

  const handleSearch = () => {
    if (!query.trim()) return
    setCompany(query.trim())
    mutation.mutate(false)
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    handleSearch()
  }

  const result = mutation.data || data
  const failedSources = missingSources(result?.partial_data)
  const sourcesReturned = SOURCE_KEYS.filter((key) => !result?.partial_data?.[key]).length
  const showSkeleton = !result && (isLoading || mutation.isPending)
  const cardVariants = reduceMotion ? fadeOnly : reveal
  const target = mutation.isPending ? (query.trim() || company) : (result?.company_name ?? company)

  const run: RunState = mutation.isPending
    ? {
        tone: 'primary',
        label: result ? 'Refreshing' : 'Researching',
        live: true,
        detail: 'The agent is reading public sources. Runs can take up to two minutes; a saved briefing stays on screen meanwhile.',
      }
    : mutation.isError
      ? {
          tone: 'danger',
          label: 'Run failed',
          live: false,
          detail: getApiErrorMessage(mutation.error, mutation.error instanceof Error ? mutation.error.message : 'The agent run did not finish.'),
        }
      : mutation.isSuccess && result
        ? failedSources.length
          ? {
              tone: 'warning',
              label: 'Partial briefing',
              live: false,
              detail: `${sourcesReturned} of ${SOURCE_KEYS.length} sources returned data for ${result.company_name}.`,
            }
          : {
              tone: 'success',
              label: 'Briefing ready',
              live: false,
              detail: `All ${SOURCE_KEYS.length} sources returned data for ${result.company_name}.`,
            }
        : result
          ? {
              tone: 'neutral',
              label: 'Saved briefing',
              live: false,
              detail: 'Restored from an earlier run. Refresh it to send the agent out again.',
            }
          : company && isLoading
            ? { tone: 'neutral', label: 'Checking saved briefings', live: true, detail: 'Looking for an earlier run on this company.' }
            : { tone: 'neutral', label: 'Idle', live: false, detail: 'Name a company to start a research run.' }

  const sentiment = (result?.glassdoor_sentiment ?? '').toLowerCase()
  const sentimentStep = SENTIMENT_SCALE.find((step) => step.value === sentiment)
  const culture = splitLead(result?.culture_summary ?? '')

  return (
    <Screen>
      <PageHero
        eyebrow="Research desk"
        title="Company dossiers"
        accent="before the first call."
        description="Brief yourself on a target employer before outreach, interviews and offer conversations. One search sends the agent out; the briefing files itself below."
        actions={
          <form role="search" aria-label="Research a company" onSubmit={handleSubmit} className="w-full max-w-2xl">
            <Bezel
              size="lg"
              lifted
              className="transition-[box-shadow] duration-500 ease-vanguard focus-within:ring-2 focus-within:ring-primary/40"
              coreClassName="flex flex-col gap-2 p-2 sm:flex-row sm:items-center"
            >
              <label htmlFor="company-search" className="sr-only">
                Company name
              </label>
              <div className="relative flex min-w-0 flex-1 items-center">
                <MagnifyingGlass
                  aria-hidden
                  size={20}
                  weight="light"
                  className="pointer-events-none absolute left-4 text-muted-foreground"
                />
                <input
                  id="company-search"
                  name="company"
                  type="text"
                  autoComplete="organization"
                  spellCheck={false}
                  className="h-14 w-full min-w-0 rounded-[1.25rem] bg-transparent pl-12 pr-4 text-lg tracking-[-0.015em] text-foreground outline-none placeholder:text-muted-foreground/60"
                  placeholder="Enter company name..."
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                />
              </div>
              <IslandButton
                type="submit"
                size="lg"
                disabled={mutation.isPending}
                icon={<Buildings size={18} weight="light" />}
                trailing
                className="w-full sm:w-auto"
              >
                {mutation.isPending ? 'Researching...' : 'Research'}
              </IslandButton>
            </Bezel>
            <p className="mt-3 pl-2 text-xs leading-5 text-muted-foreground">
              Press Enter to search. Results are cached for seven days per company.
            </p>
          </form>
        }
        aside={
          <Bezel size="lg" coreClassName="p-6 md:p-7">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Agent run</p>
              <span className="font-geist-mono text-[11px] text-muted-foreground">company_research</span>
            </div>
            <div role="status" aria-live="polite" className="mt-5 space-y-3">
              <StatusPill tone={run.tone} live={run.live}>
                {run.label}
              </StatusPill>
              <p className="text-sm leading-6 text-muted-foreground">{run.detail}</p>
            </div>
            <Hairline className="my-5" />
            <dl className="grid grid-cols-2 gap-4">
              <div className="min-w-0">
                <dt className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Target</dt>
                <dd className="mt-1.5 truncate text-sm font-medium text-foreground">{target || '—'}</dd>
              </div>
              <div className="min-w-0">
                <dt className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  <Timer aria-hidden size={12} weight="light" />
                  Elapsed
                </dt>
                <dd className="mt-1.5 text-sm text-foreground">
                  {mutation.isPending ? <ElapsedClock key={mutation.submittedAt} /> : <span className="font-geist-mono tabular-nums text-muted-foreground">--:--</span>}
                </dd>
              </div>
            </dl>
          </Bezel>
        }
      />

      {result ? (
        <Section aria-label="Company briefing">
          <SectionHeading
            eyebrow="Briefing"
            title={result.company_name}
            description={
              <>
                Last researched:{' '}
                <time dateTime={result.researched_at} className="tabular-nums">
                  {new Date(result.researched_at).toLocaleString()}
                </time>
              </>
            }
            actions={
              <IslandButton
                tone="ghost"
                size="sm"
                icon={<ArrowClockwise size={15} weight="light" />}
                onClick={() => mutation.mutate(true)}
                disabled={mutation.isPending}
              >
                Force Refresh
              </IslandButton>
            }
          />

          {failedSources.length > 0 && (
            <Notice tone="warning" icon={<WarningCircle size={16} weight="light" />}>
              Partial data — nothing found for: {failedSources.join(', ')}
            </Notice>
          )}

          <RevealGroup
            key={`${result.company_name}-${result.researched_at}`}
            className="grid grid-cols-1 gap-6 md:grid-cols-12"
          >
            {/* Lead: overview */}
            <motion.div variants={cardVariants} className="md:col-span-12 lg:col-span-8">
              <Bezel tone="primary" lifted className="h-full" coreClassName="flex h-full flex-col p-7 md:p-10">
                <PanelTitle title="Overview" icon={<GlobeHemisphereWest size={16} weight="light" />} />
                {result.overview ? (
                  <p className="mt-6 max-w-[64ch] whitespace-pre-line text-pretty text-[17px] leading-8 tracking-[-0.01em] text-foreground/85">
                    {result.overview}
                  </p>
                ) : (
                  <p className="mt-6 text-sm text-muted-foreground">Nothing came back from the company&apos;s own site.</p>
                )}
              </Bezel>
            </motion.div>

            {/* Signal readout */}
            <motion.div variants={cardVariants} className="md:col-span-12 lg:col-span-4">
              <Bezel className="h-full" coreClassName="flex h-full flex-col p-7">
                <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">At a glance</p>
                <dl className="mt-4 flex flex-1 flex-col justify-between divide-y divide-foreground/[0.07] dark:divide-white/[0.07]">
                  {[
                    { label: 'Headlines', value: result.news_items.length },
                    { label: 'Technologies', value: result.tech_stack.length },
                    { label: 'Sources returned', value: `${sourcesReturned}/${SOURCE_KEYS.length}` },
                  ].map((stat) => (
                    <div key={stat.label} className="flex items-baseline justify-between gap-4 py-4 first:pt-2 last:pb-0">
                      <dt className="text-sm text-muted-foreground">{stat.label}</dt>
                      <dd className="font-geist text-4xl font-semibold tabular-nums tracking-[-0.04em] text-foreground">{stat.value}</dd>
                    </div>
                  ))}
                </dl>
              </Bezel>
            </motion.div>

            {/* Culture — the widest reading column */}
            <motion.div variants={cardVariants} className="md:col-span-7">
              <Bezel className="h-full" coreClassName="h-full p-7 md:p-8">
                <PanelTitle title="Culture" icon={<UsersThree size={16} weight="light" />} />
                {culture.lead ? (
                  <div className="mt-6 space-y-4">
                    <p className="max-w-[48ch] text-balance font-geist text-xl font-medium leading-8 tracking-[-0.02em] text-foreground">
                      {culture.lead}
                    </p>
                    {culture.rest ? (
                      <p className="max-w-[64ch] whitespace-pre-line text-pretty text-[15px] leading-7 text-muted-foreground">{culture.rest}</p>
                    ) : null}
                  </div>
                ) : (
                  <p className="mt-6 text-sm text-muted-foreground">No workplace signals surfaced in public sources.</p>
                )}
              </Bezel>
            </motion.div>

            {/* Employee sentiment gauge */}
            <motion.div variants={cardVariants} className="md:col-span-5">
              <Bezel className="h-full" coreClassName="flex h-full flex-col p-7 md:p-8">
                <PanelTitle title="Glassdoor Sentiment" icon={<Handshake size={16} weight="light" />} />
                <div className="mt-6 flex items-center gap-4">
                  <span aria-hidden className={cn('grid h-16 w-16 shrink-0 place-items-center rounded-full bg-foreground/[0.04] ring-1 ring-foreground/[0.06] dark:bg-white/[0.05] dark:ring-white/10', sentimentStep?.text ?? 'text-foreground')}>
                    <SentimentIcon value={sentiment} />
                  </span>
                  <p className="font-geist text-4xl font-semibold capitalize tracking-[-0.04em] text-foreground md:text-5xl">
                    {result.glassdoor_sentiment || 'Unknown'}
                  </p>
                </div>
                <div className="mt-auto pt-8">
                  <div className="grid grid-cols-3 gap-1.5" aria-hidden>
                    {SENTIMENT_SCALE.map((step) => (
                      <span
                        key={step.value}
                        className={cn(
                          'h-2 rounded-full transition-colors duration-500 ease-vanguard',
                          step.value === sentiment ? step.tone : 'bg-foreground/[0.07] dark:bg-white/[0.08]',
                        )}
                      />
                    ))}
                  </div>
                  <div className="mt-2 grid grid-cols-3 text-[11px] text-muted-foreground">
                    {SENTIMENT_SCALE.map((step, i) => (
                      <span
                        key={step.value}
                        className={cn(i === 1 && 'text-center', i === 2 && 'text-right', step.value === sentiment && 'font-medium text-foreground')}
                      >
                        {step.label}
                      </span>
                    ))}
                  </div>
                  <p className="mt-4 text-xs leading-5 text-muted-foreground">Read from public employee reviews.</p>
                </div>
              </Bezel>
            </motion.div>

            {/* Technologies */}
            <motion.div variants={cardVariants} className="md:col-span-5 lg:col-span-4">
              <Bezel className="h-full" coreClassName="h-full p-7">
                <PanelTitle
                  title="Tech Stack"
                  icon={<Code size={16} weight="light" />}
                  meta={result.tech_stack.length ? <span className="tabular-nums">{result.tech_stack.length}</span> : undefined}
                />
                {result.tech_stack.length === 0 ? (
                  <p className="mt-6 text-sm text-muted-foreground">No technologies mentioned in public sources.</p>
                ) : (
                  <motion.ul variants={listStagger} className="mt-6 flex flex-wrap gap-2">
                    {result.tech_stack.map((tech, i) => (
                      <motion.li
                        key={`${tech}-${i}`}
                        variants={reduceMotion ? fadeOnly : listItem}
                        className="rounded-full bg-foreground/[0.04] px-3 py-1 font-geist-mono text-xs text-foreground/85 ring-1 ring-foreground/[0.07] dark:bg-white/[0.04] dark:ring-white/10"
                      >
                        {tech}
                      </motion.li>
                    ))}
                  </motion.ul>
                )}
              </Bezel>
            </motion.div>

            {/* Headlines */}
            <motion.div variants={cardVariants} className="md:col-span-7 lg:col-span-8">
              <Bezel className="h-full" coreClassName="h-full p-7 md:p-8">
                <PanelTitle
                  title="Recent News"
                  icon={<Newspaper size={16} weight="light" />}
                  meta={result.news_items.length ? <span className="tabular-nums">{result.news_items.length} headlines</span> : undefined}
                />
                {result.news_items.length === 0 ? (
                  <p className="mt-6 text-sm text-muted-foreground">No recent headlines found.</p>
                ) : (
                  <motion.ol
                    variants={listStagger}
                    className="mt-4 divide-y divide-foreground/[0.07] dark:divide-white/[0.07]"
                  >
                    {result.news_items.map((item, i) => {
                      const meta = [item.snippet, item.published ? new Date(item.published).toLocaleDateString() : '']
                        .filter((part) => part && part !== 'Invalid Date')
                        .join(' · ')
                      return (
                        <motion.li
                          key={i}
                          variants={reduceMotion ? fadeOnly : listItem}
                          className="grid min-w-0 grid-cols-[2rem_1fr] gap-3 py-4 last:pb-0"
                        >
                          <span aria-hidden className="pt-0.5 font-geist-mono text-xs tabular-nums text-muted-foreground/70">
                            {String(i + 1).padStart(2, '0')}
                          </span>
                          <div className="min-w-0">
                            {item.url ? (
                              <a
                                href={item.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="group inline-flex max-w-full items-start gap-1.5 break-words rounded-md font-medium tracking-[-0.01em] text-foreground transition-colors duration-500 ease-vanguard hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                              >
                                <span className="min-w-0">{item.title || 'Untitled'}</span>
                                <ArrowUpRight
                                  aria-hidden
                                  size={14}
                                  weight="light"
                                  className="mt-1 shrink-0 transition-transform duration-500 ease-vanguard group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                                />
                                <span className="sr-only">(opens in a new tab)</span>
                              </a>
                            ) : (
                              <span className="break-words font-medium tracking-[-0.01em] text-foreground">{item.title || 'Untitled'}</span>
                            )}
                            {meta && <p className="mt-1 truncate text-xs text-muted-foreground">{meta}</p>}
                          </div>
                        </motion.li>
                      )
                    })}
                  </motion.ol>
                )}
              </Bezel>
            </motion.div>
          </RevealGroup>
        </Section>
      ) : showSkeleton ? (
        <BriefingSkeleton />
      ) : (
        <Section aria-label="Company briefing">
          <Bezel tone="muted">
            <EmptyPanel
              icon={<Buildings size={24} weight="light" />}
              title="No company on the desk yet"
              description="Search for an employer above. The agent reads its site, the latest headlines, the technologies it mentions and employee reviews, then files a briefing here."
            />
          </Bezel>
        </Section>
      )}
    </Screen>
  )
}
