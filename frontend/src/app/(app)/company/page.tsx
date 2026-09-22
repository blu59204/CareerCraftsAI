'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { fadeUp, stagger } from '@/lib/motion-variants'
import { LiquidGlassButton } from '@/components/ui/LiquidGlassButton'
import { CommandHeader } from '@/components/immersive/CommandHeader'
import { apiClient, getApiErrorMessage } from '@/lib/api'
import { startAgentRun, waitForAgentRun } from '@/lib/agent-run'
import { toast } from 'sonner'
import { Building2, Globe, Newspaper, Code2 } from 'lucide-react'

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

export default function CompanyResearchPage() {
  const [query, setQuery] = useState('')
  const [company, setCompany] = useState('')

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
      const failedSources = res.partial_data ? Object.keys(res.partial_data) : []
      if (failedSources.length) {
        toast.warning(`Some sources failed: ${failedSources.join(', ')}`)
      }
    },
    onError: (error) => toast.error(getApiErrorMessage(error, error instanceof Error ? error.message : 'Research failed')),
  })

  const handleSearch = () => {
    if (!query.trim()) return
    setCompany(query.trim())
    mutation.mutate(false)
  }

  const result = mutation.data || data
  const failedSources = result?.partial_data ? Object.keys(result.partial_data) : []

  return (
    <div className="space-y-8">
      <CommandHeader
        eyebrow="AI Workflow"
        title="Company Research"
        description="Research target companies before outreach, interviews, and offer conversations."
        actions={
          <div className="flex w-full gap-2 sm:w-auto">
            <input
              className="h-10 min-w-0 flex-1 rounded-full border border-border bg-card/55 px-4 text-sm sm:w-72"
              placeholder="Enter company name..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
            <LiquidGlassButton onClick={handleSearch} disabled={mutation.isPending} size="sm">
              <Building2 className="h-4 w-4" />
              {mutation.isPending ? 'Researching...' : 'Research'}
            </LiquidGlassButton>
          </div>
        }
      />

      <div className="hidden gap-2">
        <input
          className="flex-1 rounded-md border bg-background px-3 py-2"
          placeholder="Enter company name..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
        />
        <LiquidGlassButton onClick={handleSearch} disabled={mutation.isPending}>
          {mutation.isPending ? 'Researching...' : 'Research'}
        </LiquidGlassButton>
      </div>

      {result && (
        <motion.div variants={stagger} initial="hidden" animate="show" className="grid gap-5 lg:grid-cols-2">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Last researched: {new Date(result.researched_at).toLocaleString()}</span>
            <LiquidGlassButton onClick={() => mutation.mutate(true)} disabled={mutation.isPending}>
              Force Refresh
            </LiquidGlassButton>
          </div>

          {failedSources.length > 0 && (
            <p className="text-sm text-warning">Partial data - failed sources: {failedSources.join(', ')}</p>
          )}

          <motion.section variants={fadeUp} className="glass-panel rounded-3xl p-6 lg:col-span-2">
            <h2 className="flex items-center gap-2 font-semibold"><Globe className="h-4 w-4" /> Overview</h2>
            <p className="mt-1 text-sm text-muted-foreground">{result.overview}</p>
          </motion.section>

          <motion.section variants={fadeUp} className="glass-panel rounded-3xl p-6">
            <h2 className="font-semibold">Culture</h2>
            <p className="mt-1 text-sm text-muted-foreground">{result.culture_summary}</p>
          </motion.section>

          <motion.section variants={fadeUp} className="glass-panel rounded-3xl p-6">
            <h2 className="flex items-center gap-2 font-semibold"><Newspaper className="h-4 w-4" /> Recent News</h2>
            <ul className="mt-1 list-inside list-disc text-sm text-muted-foreground">
              {result.news_items.map((item, i) => <li key={i}>{item.title || item.snippet || 'Untitled'}</li>)}
            </ul>
          </motion.section>

          <motion.section variants={fadeUp} className="glass-panel rounded-3xl p-6">
            <h2 className="flex items-center gap-2 font-semibold"><Code2 className="h-4 w-4" /> Tech Stack</h2>
            <div className="mt-1 flex flex-wrap gap-2">
              {result.tech_stack.map((tech, i) => (
                <span key={i} className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium">{tech}</span>
              ))}
            </div>
          </motion.section>

          <motion.section variants={fadeUp} className="glass-panel rounded-3xl p-6">
            <h2 className="font-semibold">Glassdoor Sentiment</h2>
            <p className="mt-1 text-sm text-muted-foreground">{result.glassdoor_sentiment}</p>
          </motion.section>
        </motion.div>
      )}

      {isLoading && !mutation.data && <p className="text-sm text-muted-foreground">Loading...</p>}
    </div>
  )
}
